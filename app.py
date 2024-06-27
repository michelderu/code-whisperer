import os
import asyncio
import json
import streamlit as st
from astrapy import DataAPIClient

from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
from astrapy.info import CollectionVectorServiceOptions

from openai import AsyncOpenAI

import reporeader

# Initialize the github repo helper class
if "repo" not in st.session_state:
    st.session_state.repo = reporeader.RepoReader()

# Initialize the tabs and placeholders
tab1, tab2, tab3, tab4 = st.tabs(["Repository data", "Overview", "Architectural summary", "Domain model"])
tab1.header("Repository data")
repository_data_placeholder = tab1.empty()
tab2.header("Overview")
overview_placeholder = tab2.empty()
tab3.header("Architectural summary")
architectural_summary_placeholder = tab3.empty()
tab4.header("Domain model")
domain_model_placeholder = tab4.empty()

# Initialize the session states
if "repository_data" not in st.session_state:
    st.session_state.repository_data = "Please select a repository first."
    st.session_state.enable_generate_documentation = False
if "overview" not in st.session_state:
    st.session_state.overview = "Please select a repository and click generate documentation."
if "architectural_summary" not in st.session_state:
    st.session_state.architectural_summary = "Please select a repository and click generate documentation."
if "domain_model" not in st.session_state:
    st.session_state.domain_model = "Please select a repository and click generate documentation."

# Cache the Astra DB Vector Store and collection
@st.cache_resource(show_spinner='Connecting to Astra')
def load_vector_store_collection():
    # Connect to the Vector Store
    client = DataAPIClient(st.secrets['ASTRA_TOKEN'])
    db = client.get_database_by_api_endpoint(st.secrets['ASTRA_API_ENDPOINT'])
    # Create or get a collection
    collection = db.create_collection(
        "uservice",
        metric=VectorMetric.COSINE,
        service=CollectionVectorServiceOptions(
            provider="openai",
            model_name="text-embedding-ada-002",
            authentication={
                "providerKey": f"{st.secrets['ASTRA_OPENAI_KEY']}.providerKey",
            },
        ),
        check_exists=False
    )
    return collection
collection = load_vector_store_collection()

async def load_sidebar():
    with st.sidebar:
        st.header("Repository")
        with st.form("github"):
            github_key = st.text_input("GitHub key", value=st.secrets['GITHUB_TOKEN'])
            github_repo = st.text_input("GitHub repo", value=st.secrets['GITHUB_REPO'])
            github_extensions = st.text_input("Process file types", value=".md, .py", help="Comma delimited string of file extensions to process")

            submitted = st.form_submit_button("Submit")
            if submitted:
                # First check if the repo has already been loaded
                result = collection.find_one(
                    {
                        "name": github_repo
                    }
                )
                if result:
                    st.warning('The provided repository has already been loaded into Astra DB. Please select another one.')
                else:
                    st.success('Reading repository and vectorizing data into Astra DB. Please hang on...')
                    st.session_state.repo.connect(github_key)
                    st.session_state.repo.setRepository(github_repo)
                    st.session_state.repo.setExtensions(github_extensions)
                    task = asyncio.create_task(generate_repository_data())
                    await task

async def generate_repository_data():
    contents_output = "The provided repository contains the following files and information:\n"
    contents = st.session_state.repo.getRepositoryContents()
    for c in contents:
        contents_output += f"- {c.name}\n"
        repository_data_placeholder.markdown(contents_output)

        # Load into Astra DB
        context = {
            "type": "vectordata",
            "name": st.session_state.repo.getName(),
            "topics": st.session_state.repo.getTopics(),
            "stars": st.session_state.repo.getStars(),
            "filename": c.name,
            "$vectorize": f"Repository name: {st.session_state.repo.getName()}\nFile name: {c.name}\nFile size: {c.size}\nContent {c.decoded_content.decode()}"            
        }
        print (context)
        collection.insert_one(context)

    st.session_state.repository_data = contents_output
    st.session_state.enable_generate_documentation = True
    task = asyncio.create_task(show_repository_data())
    await task
    
async def show_repository_data():
    print("In show_repository_data()")
    repository_data_placeholder.markdown(st.session_state.repository_data)
    if st.session_state.enable_generate_documentation:
        submitted = tab1.button("Generate documentation")
        if submitted:
            tab1.success('Generating documentation based on source code in the repository. Please hang on...')
            task = asyncio.create_task(generateDocumentation())
            await task

async def show_overview():
    overview_placeholder.markdown(st.session_state.overview)

async def show_architectural_summary():
    architectural_summary_placeholder.markdown(st.session_state.architectural_summary)

async def show_domain_model():
    domain_model_placeholder.markdown(st.session_state.domain_model)

async def generateDocumentation():
    result = await asyncio.gather(
        advisor(
            f"Generic information about the {st.session_state.repo.getName()} repository",
            "Provide a short summary of the code in a maximum of 100 words",
            overview_placeholder
        ),
        advisor(
            f"Find the main code for the {st.session_state.repo.getName()} repository",
            "Provide an architectural summary of the application",
            architectural_summary_placeholder
        ),
        advisor(
            f"Find the main code for the {st.session_state.repo.getName()} repository",
            "Show me the domain model of the chatbot service in a structured way (like uml)",
            domain_model_placeholder
        )
    )

    st.session_state.overview = result[0]
    task4 = asyncio.create_task(show_overview())
    await task4

    st.session_state.architectural_summary = result[1]
    task5 = asyncio.create_task(show_architectural_summary())
    await task5

    st.session_state.domain_model = result[2]
    task6 = asyncio.create_task(show_domain_model())
    await task6

async def advisor(search, question, placeholder):
    # First find relevant information from the Vector Database
    results = collection.find(
        {},
        vectorize=search, # embedding to search for
        limit=5,
        projection={"name", "filename"}, # only return these fields from the document
        include_similarity=True
    )

    context = []
    for result in results:
        print (f"Result: {result['filename']}")
        contents = st.session_state.repo.getRepositoryContent(result["filename"]).decoded_content.decode()
        context.append(contents)

    # Now pass the context to the Chat Completion
    client = AsyncOpenAI(api_key=st.secrets['OPENAI_API_KEY'])

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You're an IT architect and programmer specialized in migrations of microservices."},
            {"role": "system", "content": f"When constructing your answer to the question, take into account the following context: {context}"},
            {"role": "user", "content": f"Question: {question}"}
        ],
        stream=True
    )

    print(response)
    streaming_content = ""
    async for chunk in response:
        chunk_content = chunk.choices[0].delta.content
        if chunk_content is not None:
            streaming_content += chunk_content
            placeholder.markdown(f"{streaming_content}▌")

    return streaming_content[:-1]

async def main():
    task1 = asyncio.create_task(load_sidebar())
    task1 = asyncio.create_task(show_repository_data())
    task2 = asyncio.create_task(show_overview())
    task3 = asyncio.create_task(show_architectural_summary())
    task4 = asyncio.create_task(show_domain_model())
    await task1
    await task2
    await task3
    await task4

if __name__ == "__main__":
    asyncio.run(main())