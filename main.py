import os
import discord
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv
import PyPDF2
from io import BytesIO
import logging
import base64

""" ENVIRONMENT VARIABLES """

load_dotenv()

jj_discord_api_key = os.environ.get("JJ_API_KEY")
if not jj_discord_api_key:
    raise EnvironmentError("JJ_API_KEY not set in environment variables")

jay_chou_discord_api_key = os.environ.get("JAY_CHOU_API_KEY")
if not jay_chou_discord_api_key:
    raise EnvironmentError("JAY_CHOU_API_KEY not set in environment variables")

anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not anthropic_api_key:
    raise EnvironmentError("ANTHROPIC_API_KEY not set in environment variables")

anthropic_jay_chou_api_key = os.environ.get("ANTHROPIC_JAY_CHOU_API_KEY")
if not anthropic_jay_chou_api_key:
    raise EnvironmentError("ANTHROPIC_JAY_CHOU_API_KEY not set in environment variables")

""" CONFIGURE LOGGING """

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("DiscordBot")

""" ANTHROPIC CLIENTS """

# First to answer the user
anthropicClient1 = Anthropic(
    api_key=anthropic_api_key,
)

# Will answer to the first bot
anthropicClient2 = Anthropic(
    api_key=anthropic_jay_chou_api_key,
)

# response = anthropicClient1.beta.messages.create(
#     model="claude-3-5-sonnet-20241022",
#     betas=["pdfs-2024-09-25"],
#     max_tokens=1024,
#     messages=[],
#     system="",
#     top_k=3
# )

user_input = ""

async def generate_response(messages, anthropicClient, bot):

    """ Generate a response from the Anthropic API """
    
    system = ""

    if bot == "jj":

        system = f"""

            ### Role ###
            You are JJ, an AI working alongside your partner, CHOW-MEIN. 
            
            ### Goal ###
            Your primary task is to generate a specific part of the code in response to the user’s task: {user_input}. 
            You need to complete this task step by step.

            ### Output Requirements ###
            - Code Output: Generate a single, concise chunk of reusable code—such as a function, a module/class, or necessary imports.
            - Explanation: Provide a brief explanation of the purpose and use of the code.
            - Character Limit: Ensure the code snippet itself does not exceed 200 tokens. 
              The total output, including the explanation, should remain under 400 tokens.

            ### Constraints ###
            - Strict Formatting: Apply correct code formatting to ensure clarity and reusability. 
              Use code blocks to ensure that the code is visually distinct and easy to copy.
            - Token Monitoring: Actively monitor the token count during generation. 
              If the initial output exceeds 400 tokens for the code, refactor it to simplify or break down the complexity.
            - Brevity in Explanation: Keep explanations direct and to the point to conserve tokens.

        """
        
    elif bot == "jay_chou":
        system = f"""
            ### Role ###
            You are CHOW-MEIN, an AI working alongside your partner, JJ. 
            
            ### Goal ###
            Your primary task is to generate a specific part of the code in response to the user’s task: {user_input}. 
            You need to complete this task step by step.

            ### Output Requirements ###
            - Code Output: Generate a single, concise chunk of reusable code—such as a function, a module/class, or necessary imports.
            - Explanation: Provide a brief explanation of the purpose and use of the code.
            - Character Limit: Ensure the code snippet itself does not exceed 200 tokens. 
              The total output, including the explanation, should remain under 400 tokens.

            ### Constraints ###
            - Strict Formatting: Apply correct code formatting to ensure clarity and reusability. 
              Use code blocks to ensure that the code is visually distinct and easy to copy.
            - Token Monitoring: Actively monitor the token count during generation. 
              If the initial output exceeds 400 tokens for the code, refactor it to simplify or break down the complexity.
            - Brevity in Explanation: Keep explanations direct and to the point to conserve tokens.
        """
    
    try:
        logger.debug(f"Sending request to Anthropic API for bot '{bot}' with messages: {messages}")

        # response = anthropicClient.messages.create(
        #     max_tokens=4096,
        #     messages=messages,
        #     system=system,
        #     model="claude-3-5-haiku-latest",
        #     top_k=3
        # )

        response = anthropicClient.beta.messages.create(
            model = "claude-3-5-sonnet-20241022",
            # model = "claude-3-5-haiku-latest",
            betas = ["pdfs-2024-09-25"],
            max_tokens = 450,
            messages = messages,
            system = system,
            top_k = 2
        )
        
        logger.debug(f"Received response from Anthropic API: {response.content[0].text}")
        return response.content[0].text
    except Exception as e:
        logger.exception(f"Error generating response for bot '{bot}': {e}")
        return "Sorry, I encountered an error while processing your request."

""" DISCORD CLIENTS """

# Define intents
intents = discord.Intents.default()
intents.message_content = True  # Enable privileged intent if your bot needs to read message content

# Initialize Discord clients with intents
discordClient1 = discord.Client(intents=intents)
discordClient2 = discord.Client(intents=intents)

JJ_TARGET_ID = 1311735445176193094
message_history_bot_1 = []

JAY_CHOU_TARGET_ID = 1311737588544962662
message_history_bot_2 = []

@discordClient1.event
async def on_ready():
    logger.info(f'Logged in as {discordClient1.user}')

# JJ BOT (answer to the user once, then answer to the other bot)
@discordClient1.event
async def on_message(message):
    global user_input

    if message.author == discordClient1.user:
        return
    
    # Stop the bot
    if message.content.startswith('<STOP>'):
        logger.info("Received stop command.")
        return

    try:
        # Handle the first message from the user
        if len(message_history_bot_1) == 0:

            pdf_text = ""

            if message.attachments:
                attachment = message.attachments[0]
                file_bytes = await attachment.read()
                
                try:
                    # Extract text from PDF
                    pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
                    for page_num, page in enumerate(pdf_reader.pages, start=1):
                        extracted_text = page.extract_text()
                        if extracted_text:
                            pdf_text += f"--- Page {page_num} ---\n{extracted_text}\n"
                        else:
                            logger.warning(f"No text found on page {page_num} of the PDF.")
                except PyPDF2.errors.PdfReadError as e:
                    logger.error(f"Failed to read PDF: {e}")
                    await message.channel.send("Sorry, I couldn't read the PDF you uploaded.")
                    return

            print(f"Extracted PDF text: {pdf_text}")
            print(f"Message content: {message.content}")

            # Add the extracted PDF text and user message to the message history
            new_pdf_msg = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": pdf_text
                    },
                    {
                        "type": "text",
                        "text": message.content
                    }
                ]
            }

            message_history_bot_1.append(new_pdf_msg)

            user_input = message.content
            message_history_bot_1.append({ "role": "user", "content": message.content })             # Melody reads the user's first message
            message_history_bot_2.append({ "role": "user", "content": message.content })             # Melodia reads the user's first message
            logger.info(f"User input received: {user_input}")
            response = await generate_response(message_history_bot_1, anthropicClient1, "jj")
            message_history_bot_1.append({ "role": "assistant", "content": response })               # Melody writes the response
            await message.channel.send(response)
            logger.info(f"Responded to user with: {response}")
        # Handle the message from the other bot
        elif message.author.id == JAY_CHOU_TARGET_ID:
            message_history_bot_1.append({ "role": "user", "content": message.content })             # Melody reads Melodia's message
            logger.info(f"Message from JAY_CHOU_TARGET_ID: {message.content}")
            response = await generate_response(message_history_bot_1, anthropicClient1, "jj")
            message_history_bot_1.append({ "role": "assistant", "content": response })               # Melody writes the response
            await message.channel.send(response)
            logger.info(f"Responded to JAY_CHOU bot with: {response}")
    except Exception as e:
        logger.exception(f"Error in on_message for discordClient1: {e}")

# JAY CHOU BOT (answer to the other bot)
@discordClient2.event
async def on_ready():
    logger.info(f'Logged in as {discordClient2.user}')

@discordClient2.event
async def on_message(message):
    if message.author == discordClient2.user:
        return
    
    # Stop the bot
    if message.content.startswith('<STOP>'):
        logger.info("Received stop command on discordClient2.")
        return
    
    try:
        if message.author.id == JJ_TARGET_ID:
            message_history_bot_2.append({ "role": "user", "content": message.content })        # Melodia reads Melody's message
            logger.info(f"Message from JJ_TARGET_ID: {message.content}")
            response = await generate_response(message_history_bot_2, anthropicClient2, "jay_chou")
            message_history_bot_2.append({ "role": "assistant", "content": response })          # Melodia writes the response
            await message.channel.send(response)
            logger.info(f"Responded to JJ bot with: {response}")
    except Exception as e:
        logger.exception(f"Error in on_message for discordClient2: {e}")

async def main():
    try:
        logger.info("Starting Discord clients...")
        await asyncio.gather(
            discordClient1.start(jj_discord_api_key),
            discordClient2.start(jay_chou_discord_api_key)
        )
    except Exception as e:
        logger.exception(f"Error in main: {e}")
    finally:
        await discordClient1.close()
        await discordClient2.close()
        logger.info("Discord clients closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown via KeyboardInterrupt.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")