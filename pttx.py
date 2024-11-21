import streamlit as st
import requests
import openai
import os

# Set your API keys
OCR_SPACE_API_KEY = os.getenv('Space_API_KEY') # Replace with your OCR.Space API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# Custom CSS for styling
st.markdown("""
    <style>
    .title {
        font-size: 36px;
        font-weight: bold;
        color: #D6BBFC;
        text-align: center;
        margin-bottom: 5px;
    }
    .subtitle {
        font-size: 16px;
        color: #555555;
        text-align: center;
        margin-bottom: 20px;
    }
    .divider {
        border-top: 2px solid #D6BBFC;
        margin: 20px 0;
    }
    .search-button {
        background-color: #D6BBFC;
        color: white;
        font-size: 16px;
        padding: 10px;
        border-radius: 5px;
        border: none;
        width: 100%;
        cursor: pointer;
    }
    .search-button[disabled] {
        background-color: #e0e0e0;
        color: #a0a0a0;
        cursor: not-allowed;
    }
    footer {
        text-align: center;
        font-size: 12px;
        color: #555555;
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None
if "results_displayed" not in st.session_state:
    st.session_state["results_displayed"] = False

# App title and subtitle
st.markdown('<div class="title">MediNAME</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Upload an image with prescriptions or search for a medicine name directly.</div>', unsafe_allow_html=True)

# Search bar
medicine_query = st.text_input("Search for a medicine name", placeholder="Enter Medicine Name", label_visibility="collapsed")

# Divider
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# File uploader widget
uploaded_file = st.file_uploader("Upload your prescription image", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

# Validation: Only one input (search bar or file upload) should be active
if (medicine_query.strip() and uploaded_file) or (not medicine_query.strip() and not uploaded_file):
    search_disabled = True
    if medicine_query.strip() and uploaded_file:
        st.warning("Please use only one input method: either upload an image or enter a medicine name.")
    elif not medicine_query.strip() and not uploaded_file:
        st.warning("Please provide either an uploaded image or a medicine name to search.")
else:
    search_disabled = False

# Add a styled search button
if st.button("Search", disabled=search_disabled, use_container_width=True):
    st.session_state["results_displayed"] = False  # Clear previous results

    # Function to extract text from the uploaded image
    def extract_text_from_image(file):
        url = "https://api.ocr.space/parse/image"
        with open(file, "rb") as image_file:
            response = requests.post(
                url,
                files={"file": image_file},
                data={"apikey": OCR_SPACE_API_KEY, "language": "eng"}
            )
        return response.json()

    # Function to extract medicine names using ChatGPT
    def get_medicine_names(text):
        prompt = (
            f"Extract only the medicine names from the following text:\n\n{text}\n\n"
            f"Return the medicine names as a bullet-point list. Do not include any other information."
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.5,
        )
        return [med.strip() for med in response.choices[0].message.content.strip().split("\n") if med.strip()]

    # Function to get detailed info about a medicine
    def get_medicine_info(medicine_name):
        prompt = (
            f"Provide detailed and structured information about the medicine '{medicine_name}', "
            f"including:\n1. Its uses\n2. Diseases it is prescribed for\n3. Possible side effects. "
            f"Each point should be short and on point."
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()

    # Process the uploaded file if available
    if uploaded_file:
        with open("temp_image.png", "wb") as f:
            f.write(uploaded_file.read())
        try:
            result = extract_text_from_image("temp_image.png")
            extracted_text = result["ParsedResults"][0]["ParsedText"]
            medicine_names = get_medicine_names(extracted_text)
        except Exception as e:
            st.error(f"An error occurred while processing the image: {e}")
            medicine_names = []
    elif medicine_query.strip():
        # If search bar input is provided
        medicine_names = [medicine_query.strip()]
    else:
        st.warning("Please upload an image or enter a medicine name to search.")
        medicine_names = []

    # Display results
    if medicine_names:
        st.session_state["results_displayed"] = True
        st.subheader("Medicine Names")
        for medicine in medicine_names:
            with st.expander(f"Details for {medicine}"):
                info = get_medicine_info(medicine)
                st.write(info)

# Reset uploaded file if text is entered in the search bar
if medicine_query.strip():
    st.session_state["uploaded_file"] = None

# Display the uploaded image if available and no search query is entered
if uploaded_file and not medicine_query.strip():
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)

# Footer
st.markdown('<footer>Powered by OCR.Space, OpenAI, and Streamlit</footer>', unsafe_allow_html=True)
