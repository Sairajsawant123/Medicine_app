import streamlit as st
import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import openai
import re
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
st.markdown('<div class="subtitle">Upload an image with prescriptions or search for medicine names directly.</div>', unsafe_allow_html=True)

# Search bar for multiple names
medicine_query = st.text_input(
    "Search for medicine names (separate multiple names with commas)",
    placeholder="Enter Medicine Names",
    label_visibility="collapsed"
)

# Split the input into multiple names
medicine_names = [name.strip() for name in medicine_query.split(",") if name.strip()]

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

# Function to extract text from the uploaded image
def extract_text_from_image(file):
    url = "https://api.ocr.space/parse/image"
    response = requests.post(
        url,
        files={"file": file},
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

# Web scraping functions
def fetch_1mg_data(medicine_name):
    url = f"https://www.1mg.com/search/all?name={medicine_name}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    product = soup.find("div", class_="style__horizontal-card___1Zwmt")
    if product:
        name = product.find("span", class_="style__pro-title___3zxNC").text.strip()
        price_tag = product.find("div", class_="style__price-tag___B2csA")
        if price_tag:
            raw_price = price_tag.text.strip()
            # Use regex to extract only the price with symbols like $, ₹, etc.
            clean_price = re.search(r"[₹$€¥]?\d+(\.\d{1,2})?", raw_price)  # Matches currency symbols and numbers
            price = clean_price.group() if clean_price else "N/A"
        else:
            price = "N/A"
        return {"Website": "1mg", "Name": name, "Price": price}
    return {"Website": "1mg", "Name": "N/A", "Price": "N/A"}

def fetch_pharmeasy_data(medicine_name):
    url = f"https://pharmeasy.in/search/all?name={medicine_name}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    product = soup.find("div", class_="Search_medicineLists__hM5Hk")
    if product:
        name_tag = product.find("h1", class_="ProductCard_medicineName__8Ydfq")
        name = name_tag.text.strip() if name_tag else "N/A"
        # price_tag = product.find("div", class_="ProductCard_priceDiscountWrapper__UbAup")
        # price = price_tag.find_all("span")[1].text.strip() if price_tag else "N/A"
        # Updated Price and Discount section
        price_tag = product.find("div", class_=re.compile(r"ProductCard_priceContainer"))
        if price_tag:
            # Extract current price
            current_price_tag = price_tag.find("div", class_=re.compile(r"ProductCard_ourPrice"))
            price = current_price_tag.text.strip() if current_price_tag else "N/A"
            
            # Extract discount details
            discount_tag = price_tag.find("span", class_=re.compile(r"ProductCard_discountPrice"))
            discount = discount_tag.text.strip() if discount_tag else "No discount"
        if price == 'N/A':
            price_tag = product.find("div", class_="ProductCard_priceDiscountWrapper__UbAup")
            price = price_tag.find_all("span")[1].text.strip() if price_tag else "N/A"

            # Discount percentage
            discount_tag = product.find("span", class_="ProductCard_gcdDiscountPercent__oemCh")
            discount = discount_tag.text.strip() if discount_tag else "No discount"      
        return {"Website": "Pharmeasy", "Name": name, "Price": price}
    return {"Website": "Pharmeasy", "Name": "N/A", "Price": "N/A"}


def fetch_netmeds_data(medicine_name):
    url = f"https://www.netmeds.com/catalogsearch/result/{medicine_name}/all"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    product = soup.select_one("li.ais-InfiniteHits-item .cat-item")
    if product:
        name = product.find("h3", class_="clsgetname").text.strip()
        price = product.find("span", class_="final-price").text.strip()
        return {"Website": "Netmeds", "Name": name, "Price": price}
    return {"Website": "Netmeds", "Name": "N/A", "Price": "N/A"}

# Function to fetch prices
def fetch_prices(medicine_name):
    prices = []
    try:
        prices.append(fetch_1mg_data(medicine_name))
    except Exception as e:
        prices.append({"Website": "1mg", "Name": "Error", "Price": str(e)})
    try:
        prices.append(fetch_pharmeasy_data(medicine_name))
    except Exception as e:
        prices.append({"Website": "Pharmeasy", "Name": "Error", "Price": str(e)})
    try:
        prices.append(fetch_netmeds_data(medicine_name))
    except Exception as e:
        prices.append({"Website": "Netmeds", "Name": "Error", "Price": str(e)})
    return prices

# Single button to fetch data
if st.button("Search and Fetch Data", disabled=search_disabled, use_container_width=True):
    extracted_medicine_names = []

    # Process uploaded image
    if uploaded_file:
        st.info("Extracting text from the uploaded image...")
        image_data = extract_text_from_image(uploaded_file)
        if image_data.get("IsErroredOnProcessing"):
            st.error("Error processing the image. Please try again.")
        else:
            raw_text = image_data.get("ParsedResults", [{}])[0].get("ParsedText", "")
            if raw_text:
                extracted_medicine_names = get_medicine_names(raw_text)

    all_medicine_names = list(set(medicine_names + extracted_medicine_names))  # Combine inputs and remove duplicates

    if all_medicine_names:
        st.session_state["results_displayed"] = True
        for medicine in all_medicine_names:
            with st.expander(f"View details for {medicine}"):
                st.markdown(f"**Details and Prices for {medicine}:**")
                tabs = st.tabs(["Details", "Prices"])

                with tabs[0]:
                    st.subheader("Detailed Information")
                    prompt = (
                        f"Provide detailed information about the medicine '{medicine}', "
                        f"including its uses, prescribed diseases, and possible side effects."
                    )
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=300,
                        temperature=0.5,
                    )
                    details = response.choices[0].message.content.strip()
                    st.write(details)

                with tabs[1]:
                    st.subheader("Price Comparison")
                    prices = fetch_prices(medicine)
                    st.table(prices)
    else:
        st.warning("No medicine names provided or extracted. Please try again.")
