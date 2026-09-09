# AskMyDocs

**AskMyDocs** is a Retrieval-Augmented Generation (RAG) application that allows users to upload PDF documents and ask questions about their content using natural language.

The application processes uploaded PDFs, splits their content into smaller chunks, generates vector embeddings, stores them in Qdrant, retrieves relevant context for user questions, and uses Google's Gemini models to generate grounded answers.
---

## Features

*  Upload PDF documents
*  Ask questions about uploaded documents
*  Retrieval-Augmented Generation (RAG)
*  Automatic document chunking
*  Gemini-powered embeddings
*  Qdrant vector database for semantic search
*  Gemini-powered answer generation
*  Answers include relevant PDF page information
*  Uploaded PDFs are stored in Amazon S3
*  Dockerized application
*  Deployed on AWS EC2
*  Automated deployment using GitHub Actions
*  AWS infrastructure provisioned using Terraform

---

## Architecture

```text
                         ┌──────────────────────┐
                         │        User          │
                         └──────────┬───────────┘
                                    │
                                    │ Upload PDF
                                    ▼
                         ┌──────────────────────┐
                         │     AskMyDocs        │
                         │      Streamlit       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
              ┌──────────┐   ┌────────────┐   ┌─────────────┐
              │ Amazon   │   │  Gemini    │   │   Qdrant    │
              │    S3    │   │ Embeddings │   │ Vector DB   │
              └──────────┘   └────────────┘   └─────────────┘
                                    │
                                    ▼
                              Vector Search
                                    │
                                    ▼
                              Relevant Chunks
                                    │
                                    ▼
                              Gemini LLM
                                    │
                                    ▼
                              Generated Answer
```

---

## How It Works

AskMyDocs follows a typical RAG pipeline.

### 1. PDF Upload

The user uploads a PDF through the Streamlit interface.

The application temporarily saves the uploaded file and uploads a copy to Amazon S3.

```text
User
  ↓
PDF Upload
  ↓
Temporary File
  ↓
Amazon S3
```

### 2. Document Processing

The PDF is loaded using `PyPDFLoader`.

The extracted text is then split into smaller chunks using LangChain's `RecursiveCharacterTextSplitter`.

The current configuration uses:

```text
Chunk size:     1000
Chunk overlap:  200
```

### 3. Embeddings

Each text chunk is converted into a vector embedding using Google's Gemini embedding model:

```text
models/gemini-embedding-001
```

### 4. Vector Storage

The generated embeddings and associated document metadata are stored in Qdrant.

Each uploaded document receives a unique document ID, allowing searches to be restricted to the currently selected document.

```text
PDF
 ↓
Text
 ↓
Chunks
 ↓
Embeddings
 ↓
Qdrant
```

### 5. Question Answering

When the user asks a question:

```text
User Question
      ↓
Semantic Search
      ↓
Qdrant
      ↓
Relevant PDF Chunks
      ↓
Gemini
      ↓
Answer
```

The application retrieves relevant chunks from Qdrant and provides them as context to the Gemini model.

The system prompt instructs the assistant to answer using the retrieved PDF context and include relevant page numbers so the user can verify the source.

---

# Technology Stack

| Technology          | Purpose                 |
| ------------------- | ----------------------- |
| Python              | Application development |
| Streamlit           | Web interface           |
| LangChain           | RAG orchestration       |
| Google Gemini       | LLM and embeddings      |
| Qdrant              | Vector database         |
| Amazon S3           | PDF storage             |
| Docker              | Containerization        |
| Amazon EC2          | Application hosting     |
| Amazon ECR          | Docker image registry   |
| GitHub Actions      | CI/CD                   |
| AWS Systems Manager | EC2 deployment          |
| Terraform           | Infrastructure as Code  |

---

# Project Structure

```text
AskMyDocs/
│
├── .github/
│   └── workflows/
│       └── deploy.yml
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── embeddings.py
│   └── rag.py
│
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── streamlit_app.py
├── .dockerignore
└── .gitignore
```

---

# RAG Pipeline

The core document-processing pipeline is:

```text
                PDF
                 │
                 ▼
           PDF Extraction
                 │
                 ▼
          Text Chunking
                 │
                 ▼
             Embedding
                 │
                 ▼
             Qdrant
                 │
                 │
User Question ───┤
                 │
                 ▼
          Similarity Search
                 │
                 ▼
          Relevant Context
                 │
                 ▼
             Gemini
                 │
                 ▼
          Final Answer
```

---

# Docker

AskMyDocs is containerized using Docker.

The application image is built from a Python 3.12 slim base image.

The application exposes Streamlit on:

```text
8501
```

The repository also contains a Docker Compose configuration for running Qdrant.

---

# AWS Deployment

The application is deployed on AWS using an EC2-based architecture.

The main deployment flow is:

```text
Developer
    │
    ▼
GitHub
    │
    ▼
GitHub Actions
    │
    ├── Build Docker Image
    │
    ▼
Amazon ECR
    │
    ▼
AWS Systems Manager
    │
    ▼
Amazon EC2
    │
    ├── AskMyDocs Container
    │
    └── Qdrant Container
    │
    ▼
Running Application
```

The EC2 instance runs Docker and hosts the application containers.

Amazon S3 is used to store uploaded PDF files.

---

# CI/CD

The repository includes a GitHub Actions workflow that runs when changes are pushed to the `main` branch.

The deployment pipeline:

```text
git push
    │
    ▼
GitHub Actions
    │
    ▼
Configure AWS Credentials
    │
    ▼
Login to Amazon ECR
    │
    ▼
Build Docker Image
    │
    ▼
Push Image to ECR
    │
    ▼
AWS Systems Manager
    │
    ▼
EC2
    │
    ▼
Pull Latest Image
    │
    ▼
Restart Application Container
```

AWS Systems Manager is used to execute the deployment commands on the EC2 instance.

The workflow uses AWS IAM/OIDC authentication rather than requiring long-lived AWS credentials to be stored directly in GitHub.

---

# Infrastructure as Code

AWS infrastructure is defined using Terraform.

The Terraform configuration includes resources for components such as:

* VPC/networking
* Subnets
* Security groups
* EC2
* IAM roles
* S3
* GitHub Actions AWS authentication

This allows the infrastructure to be recreated and managed as code instead of being configured manually through the AWS Console.

---

# Environment Variables

The application requires environment variables for external services.

Example:

```env
GOOGLE_API_KEY=your_google_api_key

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key
```

For deployment, these values should be supplied securely through the deployment environment rather than committed to the repository.

**Never commit API keys, passwords, or other secrets to Git.**

---

# Running Locally

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd AskMyDocs
```

## 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

### Linux / macOS

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file:

```env
GOOGLE_API_KEY=your_google_api_key
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key
```

## 5. Start Qdrant

Using Docker Compose:

```bash
docker compose up -d
```

## 6. Start AskMyDocs

```bash
streamlit run streamlit_app.py
```

The application will be available through the Streamlit server.

---

# Running with Docker

Build the application image:

```bash
docker build -t askmydocs .
```

Run the container:

```bash
docker run -p 8501:8501 askmydocs
```

When running the application container alongside Qdrant, make sure the application can reach the Qdrant container through the appropriate Docker network and environment configuration.

---

# Dependencies

The project uses several libraries from the LangChain ecosystem along with Streamlit, Google Gemini, Qdrant, PDF processing, and AWS tooling.

Key dependencies include:

```text
streamlit
python-dotenv
langchain-qdrant
langchain-google-genai
langchain-community
langchain-text-splitters
pypdf
boto3
```

---

# Security Considerations

The application interacts with several external services and therefore requires careful handling of credentials.

Recommended practices:

* Never commit `.env` files containing secrets.
* Use environment variables or a secrets manager for API keys.
* Restrict AWS IAM permissions to only what the application requires.
* Avoid exposing Qdrant publicly unless required.
* Restrict EC2 security-group rules to necessary ports.
* Rotate exposed credentials immediately if they are accidentally committed.

---

# Future Improvements

Potential improvements to the project include:

*  Prometheus monitoring
*  Grafana dashboards
*  Application and infrastructure alerting
*  Application-level metrics
*  Container health checks
*  AWS Secrets Manager integration
*  Reverse proxy with HTTPS
*  Load balancing
*  Kubernetes deployment
*  Improved persistent storage for Qdrant
*  Centralized logging

---

# DevOps Implementation

AskMyDocs is also being used as a practical DevOps project to explore production-oriented concepts including:

```text
Application
    ↓
Docker
    ↓
AWS EC2
    ↓
Amazon ECR
    ↓
GitHub Actions
    ↓
AWS Systems Manager
    ↓
Terraform
    ↓
Monitoring
    ↓
Prometheus
    ↓
Grafana
```

The goal is to progressively add observability, automation, and production infrastructure to the existing RAG application.

---

## Author

**Gags-1**

Built as a practical RAG and DevOps project combining Generative AI with AWS cloud infrastructure and containerized deployment.
