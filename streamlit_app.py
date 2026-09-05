import boto3
import streamlit as st
from dotenv import load_dotenv
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.rag import process_pdf, search_pdf


# --------------------------------------------------
# Streamlit UI Setup
# --------------------------------------------------

st.set_page_config(
    page_title="AskMyDocs",
    page_icon="🤖"
)

st.title("AskMyDocs 📃")
st.write("Upload a PDF, then ask questions based on its content!")


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()


S3_BUCKET_NAME = "askmydocs-pdf-storage-031879842147"

s3 = boto3.client("s3")
# --------------------------------------------------
# Gemini LLM
# --------------------------------------------------

@st.cache_resource
def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.6-flash"
    )


llm = get_llm()


# --------------------------------------------------
# Session State
# --------------------------------------------------

if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

if "document_id" not in st.session_state:
    st.session_state.document_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------
# PDF Upload
# --------------------------------------------------

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type="pdf"
)


# --------------------------------------------------
# Process Uploaded PDF
# --------------------------------------------------

if uploaded_file is not None and st.session_state.vector_db is None:

    st.info("Processing PDF... This might take a moment.")

    temp_dir = "temp_uploaded_pdfs"

    os.makedirs(
        temp_dir,
        exist_ok=True
    )

    temp_file_path = os.path.join(
        temp_dir,
        uploaded_file.name
    )

    # Save uploaded PDF temporarily
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Upload PDF to S3
    s3.upload_file(
        temp_file_path,
        S3_BUCKET_NAME,
        uploaded_file.name
    )
    try:

        with st.spinner(
            "Creating vector database from PDF content..."
        ):

            # Our RAG module handles:
            #
            # PDF loading
            # ↓
            # Text splitting
            # ↓
            # Embeddings
            # ↓
            # Qdrant
            #
            st.session_state.vector_db, st.session_state.document_id = process_pdf(
    temp_file_path
)


        st.success(
            "PDF processed and vector database ready!"
        )

        # Initialize conversation
        st.session_state.messages = []

        st.session_state.messages.append(
            SystemMessage(
                content="""
You are a helpful AI Assistant who answers user queries based on the
available context retrieved from a PDF file along with page contents
and page number.

You should only answer the user based on the provided context.

When answering questions, mention the relevant page number so the user
can navigate to the original PDF and verify the information.

If the user specifically says they do not understand something,
make it simpler and explain it using examples or real-life scenarios,
ONLY IF THE USER ASKS.
"""
            )
        )

        st.session_state.messages.append(
            AIMessage(
                content="I have processed the PDF. How can I help you with its content?"
            )
        )

    finally:

        # Delete temporary PDF
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # Delete temporary directory if empty
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)


# --------------------------------------------------
# Chat Interface
# --------------------------------------------------

if st.session_state.vector_db is not None:

    # Display previous messages
    for message in st.session_state.messages:

        if isinstance(message, HumanMessage):

            with st.chat_message("user"):
                st.markdown(message.content)

        elif isinstance(message, AIMessage):

            with st.chat_message("assistant"):
                st.markdown(message.content)


    # Get user's question
    if prompt := st.chat_input(
        "What would you like to know about the PDF?"
    ):

        # Save user message
        st.session_state.messages.append(
            HumanMessage(
                content=prompt
            )
        )

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)


        # Generate answer
        with st.chat_message("assistant"):

            with st.spinner("Thinking..."):

                # ------------------------------------------
                # Retrieve relevant chunks
                # ------------------------------------------

                search_results = search_pdf(
 		   st.session_state.vector_db,
    		   prompt,
    		   st.session_state.document_id
		)


                # ------------------------------------------
                # Build context
                # ------------------------------------------

                current_turn_context = "\n\n\n".join(
                    [
                        f"""
Page Content:
{result.page_content}

Page Number:
{result.metadata['page_label']}

File Location:
{result.metadata['source']}
"""
                        for result in search_results
                    ]
                )


                # ------------------------------------------
                # Create system message
                # ------------------------------------------

                current_system_message = SystemMessage(
                    content=(
                        st.session_state.messages[0].content
                        + "\n\nContext:\n"
                        + current_turn_context
                    )
                )


                # ------------------------------------------
                # Prepare conversation
                # ------------------------------------------

                messages_to_send = (
                    [current_system_message]
                    + st.session_state.messages[1:]
                )


                # ------------------------------------------
                # Send request to Gemini
                # ------------------------------------------

                chat_completion = llm.invoke(
                    messages_to_send
                )


                # ------------------------------------------
                # Extract response
                # ------------------------------------------

                raw_content = chat_completion.content

                if isinstance(raw_content, str):

                    ai_response_content = raw_content

                elif isinstance(raw_content, list):

                    text_parts = []

                    for block in raw_content:

                        if isinstance(block, dict):

                            if block.get("type") == "text":

                                text_parts.append(
                                    block.get("text", "")
                                )

                        else:

                            text_parts.append(
                                str(block)
                            )

                    ai_response_content = "\n".join(
                        text_parts
                    ).strip()

                else:

                    ai_response_content = str(
                        raw_content
                    )


                # ------------------------------------------
                # Display response
                # ------------------------------------------

                st.markdown(
                    ai_response_content
                )


                # ------------------------------------------
                # Save response to chat history
                # ------------------------------------------

                st.session_state.messages.append(
                    AIMessage(
                        content=ai_response_content
                    )
                )
