import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Dynamic RAG Chatbot", page_icon="🤖")
st.title("AskMyDocs📃")
st.write("Upload a PDF, then ask questions based on its content!")

# --- Configuration and Initialization ---
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

TEMP_QDRANT_COLLECTION_NAME = "user_uploaded_pdf_vectors"

@st.cache_resource
def get_embedding_model():
    return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

@st.cache_resource
def get_llm():
    return ChatGoogleGenerativeAI(model="gemini-3.6-flash")

embedding_model = get_embedding_model()
llm = get_llm()

# --- PDF Upload and Processing Logic ---
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None
if "messages" not in st.session_state:
    st.session_state.messages = []

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None and st.session_state.vector_db is None:
    st.info("Processing PDF... This might take a moment.")
    
    temp_dir = "temp_uploaded_pdfs"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, uploaded_file.name)

    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        loader = PyPDFLoader(file_path=temp_file_path)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        split_docs = text_splitter.split_documents(documents=docs)

        with st.spinner("Creating vector database from PDF content..."):
            st.session_state.vector_db = QdrantVectorStore.from_documents(
                documents=split_docs,
                url=QDRANT_URL,
                collection_name=TEMP_QDRANT_COLLECTION_NAME,
                embedding=embedding_model,
                force_recreate=True,
                api_key=QDRANT_API_KEY
            )
        st.success("PDF processed and vector database ready! You can now ask questions.")

        st.session_state.messages = []
        st.session_state.messages.append(SystemMessage(content="""
            You are a helpful AI Assistant who answers user queries based on the available context
            retrieved from a PDF file along with page_contents and page number.

            You should only answer the user based on the following context and navigate the user
            to open the right page number to know more.

            If the user specifically says they donot understand something, make it simpler and make it understanble by giving examps or real life scenarios, ONLY IF THE USER ASKS
        """))
        st.session_state.messages.append(AIMessage(content="I have processed the PDF. How can I help you with its content?"))

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)

# --- Chat Interface ---
if st.session_state.vector_db is not None:

    # Display previous messages
    for message in st.session_state.messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(message.content)

        elif isinstance(message, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(message.content)

    # Get new user question
    if prompt := st.chat_input("What would you like to know about the PDF?"):

        # Store the user's question
        st.session_state.messages.append(
            HumanMessage(content=prompt)
        )

        # Display user's question
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate answer
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):

                # Search Qdrant for relevant PDF chunks
                search_results = st.session_state.vector_db.similarity_search(
                    query=prompt
                )

                # Build context from retrieved chunks
                current_turn_context = "\n\n\n".join([
                    f"Page Content: {result.page_content}\n"
                    f"Page Number: {result.metadata['page_label']}\n"
                    f"File Location: {result.metadata['source']}"
                    for result in search_results
                ])

                # Create system message containing the retrieved context
                current_system_message = SystemMessage(
                    content=(
                        st.session_state.messages[0].content
                        + "\n\nContext:\n"
                        + current_turn_context
                    )
                )

                # The current prompt is already inside messages.
                # Do NOT append HumanMessage(content=prompt) again.
                messages_to_send = (
                    [current_system_message]
                    + st.session_state.messages[1:]
                )

                # Send conversation to Gemini
                chat_completion = llm.invoke(messages_to_send)

                # Gemini can return either:
                # 1. A normal string
                # 2. A list of content blocks
                raw_content = chat_completion.content

                if isinstance(raw_content, str):
                    ai_response_content = raw_content

                elif isinstance(raw_content, list):
                    text_parts = []

                    for block in raw_content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        else:
                            text_parts.append(str(block))

                    ai_response_content = "\n".join(text_parts).strip()

                else:
                    ai_response_content = str(raw_content)

                # Display clean response
                st.markdown(ai_response_content)

                # Store clean response in conversation history
                st.session_state.messages.append(
                    AIMessage(content=ai_response_content)
                )
