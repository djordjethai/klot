import mysql
import os
import streamlit as st
import uuid

from openai import OpenAI

from myfunc.asistenti import read_aad_username
from myfunc.mojafunkcija import positive_login
from myfunc.prompts import ConversationDatabase, PromptDatabase
from myfunc.retrievers import HybridQueryProcessor

client=OpenAI()
processor = HybridQueryProcessor(api_key=os.getenv("PINECONE_API_KEY"), namespace='positive') # namespace moze i iz env

if "init_prompt" not in st.session_state:
    st.session_state.init_prompt = 42
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["user_prompt", "system_prompt"],[os.getenv("CHAT_TOOLS_PROMPT"), os.getenv("ALT_ASISTENT")])
        st.session_state.user_prompt = prompt_map.get("user_prompt", "You are helpful assistant")
        st.session_state.system_prompt = prompt_map.get("system_prompt", "You are helpful assistant")
    
def main():
    if "username" not in st.session_state:
        st.session_state.username = "positive"
    if deployment_environment == "Azure":    
        st.session_state.username = read_aad_username()
    elif deployment_environment == "Windows":
        st.session_state.username = "lokal"
    elif deployment_environment == "Streamlit":
        st.session_state.username = username

    if "client" not in st.session_state:
        st.session_state.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-4-turbo-preview"
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = st.session_state.system_prompt
    if "azure_filename" not in st.session_state:
        st.session_state.azure_filename = "altass.csv"
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "app_name" not in st.session_state:
        st.session_state.app_name = "KlotBot"
    if "thread_id" not in st.session_state:
        def get_thread_ids():
            with ConversationDatabase() as db:
                return db.list_threads(st.session_state.app_name, st.session_state.username)
        new_thread_id = str(uuid.uuid4())
        thread_name = f"Thread_{new_thread_id}"
        conversation_data = [{'role': 'system', 'content': st.session_state.system_prompt}]
        if thread_name not in get_thread_ids():
            with ConversationDatabase() as db:
                try:
                    db.add_sql_record(st.session_state.app_name, st.session_state.username, thread_name, conversation_data)
                except mysql.connector.IntegrityError as e:
                    if e.errno == 1062:  # Duplicate entry for key
                        st.error("Thread ID already exists. Please try again with a different ID.")
                    else:
                        raise  # Re-raise the exception if it's not related to a duplicate entry
        st.session_state.thread_id = thread_name
        st.session_state.messages[thread_name] = []
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = st.session_state.system_prompt
        st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.system_prompt})
    
    avatar_ai="bot.png" 
    avatar_user = "user.webp"
    avatar_sys = "positivelogo.jpg"
   
    #with st.sidebar:
    #    st.info(f"Prijavljeni ste kao: {st.session_state.username}")

    if st.session_state.thread_id is None:
        st.info("Start a conversation by selecting a new or existing conversation.")
    else:
        current_thread_id = st.session_state.thread_id
        # Check if there's an existing conversation in the session state
        if current_thread_id not in st.session_state.messages:
            # If not, initialize it with the conversation from the database or as an empty list
            with ConversationDatabase() as db:
                st.session_state.messages[current_thread_id] = db.query_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id) or []
        if current_thread_id in st.session_state.messages:
            # avatari primena
            for message in st.session_state.messages[current_thread_id]:
                if message["role"] == "assistant": 
                    with st.chat_message(message["role"], avatar=avatar_ai):
                            st.markdown(message["content"])
                elif message["role"] == "user":         
                    with st.chat_message(message["role"], avatar=avatar_user):
                            st.markdown(message["content"])
                else:         
                    with st.chat_message(message["role"], avatar=avatar_sys):
                            st.markdown(message["content"])
    # Main conversation UI
    if prompt := st.chat_input("Kako vam mogu pomoci?"):
    
        # Original processing to generate complete_prompt
        context, scores = processor.process_query_results(prompt)
        complete_prompt = st.session_state.user_prompt.format(prompt=prompt, context=context)
    
        # Append only the user's original prompt to the actual conversation log
        st.session_state.messages[current_thread_id].append({"role": "user", "content": prompt})
    
        # Display user prompt in the chat
        with st.chat_message("user", avatar=avatar_user):
            st.markdown(prompt)
        
        # Prepare a temporary messages list for generating the assistant's response
        temp_messages = st.session_state.messages[current_thread_id].copy()
        temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    
        # Generate and display the assistant's response using the temporary messages list
        with st.chat_message("assistant", avatar=avatar_ai):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model="gpt-4-turbo-preview",
                temperature=0,
                messages=temp_messages,  # Use the temporary list with enriched context
                stream=True,
            ):
                full_response += (response.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        # Append assistant's response to the conversation
        st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})

        with ConversationDatabase() as db:
            db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])

deployment_environment = os.environ.get("DEPLOYMENT_ENVIRONMENT")

if deployment_environment == "Streamlit":
    name, authentication_status, username = positive_login(main, " ")
else:
    if __name__ == "__main__":
        main()