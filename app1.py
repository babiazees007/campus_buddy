import streamlit as st
import google.generativeai as genai
import os
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Google Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Database connection
def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Babiazees@123",
        database="campus_buddy"
    )
    return conn

# MySQL Table Creation Commands:
# CREATE TABLE resources (id INT AUTO_INCREMENT PRIMARY KEY, category VARCHAR(255), name VARCHAR(255), file_path VARCHAR(255));
# CREATE TABLE schedules (id INT AUTO_INCREMENT PRIMARY KEY, type VARCHAR(255), name VARCHAR(255), details TEXT);
# CREATE TABLE classrooms (id INT AUTO_INCREMENT PRIMARY KEY, room_number VARCHAR(50), details TEXT);
# CREATE TABLE calendar (id INT AUTO_INCREMENT PRIMARY KEY, date DATE, event TEXT);

# Function to get AI response
def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    return response.text

# Function to find matching resource with enhanced search capabilities
def find_resource(category, name):
    conn = get_db_connection()
    cursor = conn.cursor()

    # First try exact matching
    cursor.execute("SELECT file_path FROM resources WHERE category=%s AND name LIKE %s", (category, f"%{name}%"))
    result = cursor.fetchone()

    # If no exact match, try more flexible matching
    if not result and name:
        # Split the search query into words
        search_terms = name.lower().split()

        # Get all resources in this category
        cursor.execute("SELECT id, name, file_path FROM resources WHERE category=%s", (category,))
        all_resources = cursor.fetchall()

        best_match = None
        highest_score = 0

        # Score each resource based on how many search terms it contains
        for res_id, res_name, res_path in all_resources:
            res_name_lower = res_name.lower()
            score = 0

            # Check for each search term
            for term in search_terms:
                # Handle common abbreviations and variations
                if term in res_name_lower:
                    score += 1
                # Handle semester abbreviations (sem, semester)
                elif term.isdigit() and (f"semester {term}" in res_name_lower or f"sem {term}" in res_name_lower):
                    score += 1
                # Handle year abbreviations
                elif term.isdigit() and (f"year {term}" in res_name_lower or f"{term}rd year" in res_name_lower or f"{term}nd year" in res_name_lower or f"{term}st year" in res_name_lower or f"{term}th year" in res_name_lower):
                    score += 1
                # Handle ordinal numbers (1st, 2nd, 3rd, etc.)
                elif term.endswith(('st', 'nd', 'rd', 'th')) and term[:-2].isdigit():
                    num = term[:-2]
                    if num in res_name_lower or f"semester {num}" in res_name_lower or f"year {num}" in res_name_lower:
                        score += 1

            # If this resource has a better match score, update our best match
            if score > highest_score and score > 0:
                highest_score = score
                best_match = res_path

        # If we found a match with our enhanced search
        if best_match:
            result = (best_match,)

    conn.close()
    return result[0] if result else None

# Function to get today's events
def get_todays_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT event FROM calendar WHERE date=%s", (today,))
    results = cursor.fetchall()
    conn.close()
    return [result[0] for result in results] if results else None

# Function to get classroom details
def get_classroom_details(room_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT details FROM classrooms WHERE room_number LIKE %s", (f"%{room_number}%",))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Function to determine file type and MIME type
def get_file_mime_type(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension == '.pdf':
        return "application/pdf"
    elif extension == '.jpg' or extension == '.jpeg':
        return "image/jpeg"
    elif extension == '.png':
        return "image/png"
    else:
        return "application/octet-stream"

# Admin Page for Uploads and Management
if "admin" in st.query_params:
    st.title("📂 Admin Panel - Manage Campus Resources")

    # Create tabs for different admin functions
    tab1, tab2 = st.tabs(["Upload New Resources", "Manage Existing Resources"])

    with tab1:
        category = st.selectbox("Select Category", ["PDFs", "Class Timetables", "Event Schedules", "Exam Timetables", "Classroom Numbers", "Working Days & Holidays"])
        name = st.text_input("Enter Name/Title")

        # Allow different file types based on category
        if category in ["Class Timetables", "Exam Timetables"]:
            uploaded_file = st.file_uploader("Upload File", type=["jpg", "jpeg", "png", "pdf"])
        else:
            uploaded_file = st.file_uploader("Upload File", type=["pdf"])

        details = st.text_area("Enter Details (Optional)")

        if st.button("Upload") and name:
            conn = get_db_connection()
            cursor = conn.cursor()

            if category in ["PDFs", "Class Timetables", "Event Schedules", "Exam Timetables"] and uploaded_file:
                # Create uploads directory if it doesn't exist
                os.makedirs("uploads", exist_ok=True)

                # Generate a unique filename to avoid overwriting
                file_extension = os.path.splitext(uploaded_file.name)[1]
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                safe_filename = f"{name.replace(' ', '_')}_{timestamp}{file_extension}"

                save_path = os.path.join("uploads", safe_filename)
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                cursor.execute("INSERT INTO resources (category, name, file_path) VALUES (%s, %s, %s)", (category, name, save_path))
            elif category == "Classroom Numbers":
                cursor.execute("INSERT INTO classrooms (room_number, details) VALUES (%s, %s)", (name, details))
            elif category == "Working Days & Holidays":
                try:
                    # Try to parse the date
                    date_obj = datetime.strptime(name, '%Y-%m-%d')
                    cursor.execute("INSERT INTO calendar (date, event) VALUES (%s, %s)", (name, details))
                except ValueError:
                    st.error("Date must be in YYYY-MM-DD format")
                    conn.close()
                    st.stop()

            conn.commit()
            conn.close()
            st.success(f"{name} uploaded successfully!")

    with tab2:
        manage_category = st.selectbox("Select Category to Manage",
                                      ["PDFs", "Class Timetables", "Event Schedules", "Exam Timetables", "Classroom Numbers", "Working Days & Holidays"],
                                      key="manage_category")

        conn = get_db_connection()
        cursor = conn.cursor()

        if manage_category in ["PDFs", "Class Timetables", "Event Schedules", "Exam Timetables"]:
            cursor.execute("SELECT id, name, file_path FROM resources WHERE category=%s", (manage_category,))
            resources = cursor.fetchall()

            if resources:
                st.write(f"### Existing {manage_category}")
                for res_id, res_name, res_path in resources:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{res_name}**")
                    with col2:
                        if st.button(f"Update", key=f"update_{res_id}"):
                            st.session_state.update_id = res_id
                            st.session_state.update_name = res_name
                            st.session_state.update_path = res_path
                    with col3:
                        if st.button(f"Delete", key=f"delete_{res_id}"):
                            # Delete the file if it exists
                            if os.path.exists(res_path):
                                os.remove(res_path)
                            cursor.execute("DELETE FROM resources WHERE id=%s", (res_id,))
                            conn.commit()
                            st.success(f"Deleted {res_name}")
                            st.experimental_rerun()
                            st.rerun()

                # Handle update operation
                if "update_id" in st.session_state:
                    st.write("### Update Resource")
                    new_name = st.text_input("New Name", value=st.session_state.update_name)
                    new_file = st.file_uploader("Upload New File", key="update_file")

                    if st.button("Save Changes"):
                        if new_file:
                            # Delete old file if it exists
                            if os.path.exists(st.session_state.update_path):
                                os.remove(st.session_state.update_path)

                            # Save new file
                            file_extension = os.path.splitext(new_file.name)[1]
                            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                            safe_filename = f"{new_name.replace(' ', '_')}_{timestamp}{file_extension}"

                            save_path = os.path.join("uploads", safe_filename)
                            with open(save_path, "wb") as f:
                                f.write(new_file.getbuffer())

                            cursor.execute("UPDATE resources SET name=%s, file_path=%s WHERE id=%s",
                                          (new_name, save_path, st.session_state.update_id))
                        else:
                            cursor.execute("UPDATE resources SET name=%s WHERE id=%s",
                                          (new_name, st.session_state.update_id))

                        conn.commit()
                        st.success("Resource updated successfully!")
                        # Clear the session state
                        del st.session_state.update_id
                        del st.session_state.update_name
                        del st.session_state.update_path
                        st.experimental_rerun()
            else:
                st.info(f"No {manage_category} found in the database.")

        elif manage_category == "Classroom Numbers":
            cursor.execute("SELECT id, room_number, details FROM classrooms")
            classrooms = cursor.fetchall()

            if classrooms:
                st.write("### Existing Classrooms")
                for room_id, room_number, details in classrooms:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{room_number}**: {details[:50]}...")
                    with col2:
                        if st.button(f"Update", key=f"update_room_{room_id}"):
                            st.session_state.update_room_id = room_id
                            st.session_state.update_room_number = room_number
                            st.session_state.update_room_details = details
                    with col3:
                        if st.button(f"Delete", key=f"delete_room_{room_id}"):
                            cursor.execute("DELETE FROM classrooms WHERE id=%s", (room_id,))
                            conn.commit()
                            st.success(f"Deleted classroom {room_number}")
                            st.experimental_rerun()

                # Handle update operation for classrooms
                if "update_room_id" in st.session_state:
                    st.write("### Update Classroom")
                    new_room_number = st.text_input("New Room Number", value=st.session_state.update_room_number)
                    new_details = st.text_area("New Details", value=st.session_state.update_room_details)

                    if st.button("Save Classroom Changes"):
                        cursor.execute("UPDATE classrooms SET room_number=%s, details=%s WHERE id=%s",
                                      (new_room_number, new_details, st.session_state.update_room_id))
                        conn.commit()
                        st.success("Classroom updated successfully!")
                        # Clear the session state
                        del st.session_state.update_room_id
                        del st.session_state.update_room_number
                        del st.session_state.update_room_details
                        st.experimental_rerun()
            else:
                st.info("No classrooms found in the database.")

        elif manage_category == "Working Days & Holidays":
            cursor.execute("SELECT id, date, event FROM calendar ORDER BY date")
            calendar_events = cursor.fetchall()

            if calendar_events:
                st.write("### Existing Calendar Events")
                for event_id, date, event_desc in calendar_events:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{date}**: {event_desc[:50]}...")
                    with col2:
                        if st.button(f"Update", key=f"update_event_{event_id}"):
                            st.session_state.update_event_id = event_id
                            st.session_state.update_event_date = date
                            st.session_state.update_event_desc = event_desc
                    with col3:
                        if st.button(f"Delete", key=f"delete_event_{event_id}"):
                            cursor.execute("DELETE FROM calendar WHERE id=%s", (event_id,))
                            conn.commit()
                            st.success(f"Deleted event on {date}")
                            st.experimental_rerun()

                # Handle update operation for calendar events
                if "update_event_id" in st.session_state:
                    st.write("### Update Calendar Event")
                    new_date = st.text_input("New Date (YYYY-MM-DD)", value=st.session_state.update_event_date)
                    new_event_desc = st.text_area("New Event Description", value=st.session_state.update_event_desc)

                    if st.button("Save Event Changes"):
                        try:
                            # Validate date format
                            datetime.strptime(new_date, '%Y-%m-%d')
                            cursor.execute("UPDATE calendar SET date=%s, event=%s WHERE id=%s",
                                          (new_date, new_event_desc, st.session_state.update_event_id))
                            conn.commit()
                            st.success("Calendar event updated successfully!")
                            # Clear the session state
                            del st.session_state.update_event_id
                            del st.session_state.update_event_date
                            del st.session_state.update_event_desc
                            st.experimental_rerun()
                        except ValueError:
                            st.error("Date must be in YYYY-MM-DD format")
            else:
                st.info("No calendar events found in the database.")

        conn.close()

    st.stop()

# Set up Streamlit UI
st.set_page_config(page_title="CODE AVENGERS", layout="wide")
st.title("🤖 Campus Buddy - AI Powered Chatbot for Smart Learning")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input
user_input = st.chat_input("Ask me anything...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Enhanced categories mapping with more variations
    categories = {
        "pdf": "PDFs",
        "timetable": "Class Timetables",
        "time table": "Class Timetables",
        "class schedule": "Class Timetables",
        "schedule": "Class Timetables",
        "event schedule": "Event Schedules",
        "event": "Event Schedules",
        "exam timetable": "Exam Timetables",
        "exam schedule": "Exam Timetables",
        "exam time table": "Exam Timetables",
        "examination": "Exam Timetables",
        "classroom": "Classroom Numbers",
        "room": "Classroom Numbers",
        "class": "Classroom Numbers",
        "holidays": "Working Days & Holidays",
        "holiday": "Working Days & Holidays",
        "working days": "Working Days & Holidays",
        "calendar": "Working Days & Holidays"
    }
    ai_response = ""

    # Check for today's events
    if "today" in user_input.lower() and ("event" in user_input.lower() or "schedule" in user_input.lower()):
        events = get_todays_events()
        if events:
            ai_response = f"Today's events:\n" + "\n".join([f"• {event}" for event in events])
        else:
            ai_response = "There are no events scheduled for today."

    # Check for classroom details
    elif any(keyword in user_input.lower() for keyword in ["classroom", "room", "class"]):
        # Extract room number - enhanced approach
        query = user_input.lower()
        for keyword in ["classroom", "room", "class"]:
            query = query.replace(keyword, "")

        query = query.strip()
        words = query.split()

        # First try to find rooms with numbers
        for word in words:
            if any(c.isdigit() for c in word):
                room_details = get_classroom_details(word)
                if room_details:
                    ai_response = f"Classroom {word} details:\n{room_details}"
                    break

        # If no room found by number, try the whole query
        if not ai_response:
            room_details = get_classroom_details(query)
            if room_details:
                ai_response = f"Classroom details:\n{room_details}"
            else:
                ai_response = "Sorry, I couldn't find details for that classroom."

    # Check for resources with enhanced matching
    else:
        # First, check for exact category matches
        matched_category = None
        query_name = user_input

        for key, category in categories.items():
            if key in user_input.lower():
                matched_category = category
                query_name = user_input.lower().replace(key, "").strip()
                break

        # If no exact category match but contains educational terms, try timetables
        if not matched_category:
            educational_terms = ["semester", "sem", "year", "course", "branch", "department", "cse", "it", "ece", "mech", "civil"]
            if any(term in user_input.lower() for term in educational_terms):
                # Check if it might be an exam timetable
                if any(term in user_input.lower() for term in ["exam", "final", "mid", "test"]):
                    matched_category = "Exam Timetables"
                else:
                    matched_category = "Class Timetables"
                query_name = user_input

        # If we identified a category, search for the resource
        if matched_category:
            resource_path = find_resource(matched_category, query_name)
            if resource_path:
                file_name = os.path.basename(resource_path)
                mime_type = get_file_mime_type(resource_path)

                with open(resource_path, "rb") as file:
                   file_data = file.read()

                # For images, display them directly
                if mime_type.startswith("image/"):
                    st.image(file_data, caption=file_name)
                    ai_response = f"Here is the {matched_category.lower()} for {query_name}:"
                else:
                    # For PDFs and other files, provide download button
                    st.download_button(
                        label=f"📄 Download {file_name}",
                        data=file_data,
                        file_name=file_name,
                        mime=mime_type
                    )
                    ai_response = f"Here is the {matched_category.lower()} for {query_name}:"
            else:
                ai_response = f"Sorry, I couldn't find the requested {matched_category.lower()}"

    if not ai_response:
        ai_response = get_gemini_response(user_input)

    st.session_state.messages.append({"role": "assistant", "content": ai_response})
    with st.chat_message("assistant"):
        st.write(ai_response)
