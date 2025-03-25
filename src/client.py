import os
import openai
from groq import Groq
import logging
from config import Config
import time
import httpx

logger = logging.getLogger(__name__)

# initialize client
def initialize_client(logger = logger):
    if Config.CLIENT_CHOICE == '1':
        client = openai.OpenAI(api_key = Config.OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
    elif Config.CLIENT_CHOICE == '2':
        client = Groq(api_key= Config.GROQ_API_KEY)
        logger.info("Groq client initialized")
    return client

# Transcribe using OpenAI
def transcribe_openai(audio_path, client, language="no_language", translation_language="no_translation", logger = logger):
    """"Transcribe audio using OpenAI's Whisper model"""
    logger.info(f"Starting OpenAi transcription for file: {audio_path}")
    with open(audio_path, 'rb') as audio_file:
        transcription_params = {
            "model": Config.OPENAI_MODEL,
            "file": audio_file,
            "response_format": Config.VERBOSE,
            "temperature": Config.TEMPERATURE,
        }
        if language != "no_language":
            transcription_params["language"] = language
        transcription = client.audio.transcriptions.create(**transcription_params)
    logger.info(f"Transcription completed for file: {audio_path}")
    return transcription.text

# Transcribe using Groq
def transcribe_groq(audio_path, client, language="no_language", translation_language="no_translation", logger = logger):
    """"Transcribe audio using Groq's model"""
    logger.info(f"Starting Groq transcription for file: {audio_path}")
    with open(audio_path, "rb") as file:
        # Create a transcription of the audio file
        transcription_params = {
            "file": (audio_path, file.read()),  # Required audio file
            "response_format": Config.GROQ_RESPONSE_FORMAT,  # Optional
            "temperature": Config.GROQ_TEMPERATURE,  # Optional
        }
                
        # How it works if we only want to use the light model
        transcription_params["model"] = Config.GROQ_MODEL_LIGHT
        if language != "no_language":
            if translation_language != "no_translation":
                # How we are using this and it somehow works in english
                transcription_params["language"] = translation_language
            else:
                # How it is supposed to be (the language param is supposed to be the language of the audio)
                transcription_params["language"] = language
        transcription=client.audio.transcriptions.create(**transcription_params)
        
        # How it is supposed to work using the heavier models for translation, 
        # which is supposed to be better but sadly it doesn't work
        
        # if translation_language == "no_translation":
        #     if language != "no_language":
        #         transcription_params["language"] = language
        #     transcription_params["model"] = Config.GROQ_MODEL_LIGHT
        #     transcription = client.audio.transcriptions.create(**transcription_params)
        # else:
        #     # transcription_params["language"] = translation_language # does not exist, only support english
        #     transcription_params["model"] = Config.GROQ_MODEL
        #     transcription = client.audio.translations.create(**transcription_params)
            
    srt = GenerateSRTFromGroq(transcription.segments, logger)
    return transcription.text, srt

def Transcribe_WithGroq_SingleChunk(client, chunk, chunk_num, total_chunks, language = 'en'):
    """Transcribe a single audio chunk with Groq API."""
    total_api_time = 0
    
    while True:
        start_time = time.time()
        try:
            if language == "do not know" or language == "none of the above":
                result = client.audio.transcriptions.create(
                file=("chunk.flac", chunk, "audio/flac"),
                model="whisper-large-v3",
                response_format="verbose_json"
                )
            else:
                result = client.audio.transcriptions.create(
                    file=("chunk.flac", chunk, "audio/flac"),
                    model="whisper-large-v3",
                    language=language,
                    response_format="verbose_json"
                    )
            api_time = time.time() - start_time
            total_api_time += api_time
            return result, total_api_time
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # If rate limited error, wait for 60 seconds and try again
                time.sleep(60)
                continue
            else:
                raise RuntimeError(f"Error transcribing chunk {chunk_num}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error transcribing chunk {chunk_num}: {str(e)}")

def GenerateSRTFromGroq(segments, logger = logger):
    """Generate SRT file from Groq's transcriptions"""
    logger.info("Generating SRT file from Groq transcriptions")
    srt = ''
    
    # harmonizers because of the chunks 
    last_id = 0
    last_end_time = 0.0
    time_cursor = 0.0
    id_cursor = 1
    
    for segment in segments:
        # Harmonize the start_time, end_time, and id if they go back to 0
        if segment['id'] == 0 and segment['start'] == 0:
            id_cursor += last_id
            time_cursor += last_end_time
        
        start_time = segment['start'] + time_cursor
        end_time = segment['end'] + time_cursor
        text = segment['text'].lstrip()  # Remove leading space
        id = segment['id'] + id_cursor
        
        # Convert start and end times to SRT format
        start_srt = f"{int(start_time // 3600):02}:{int((start_time % 3600) // 60):02}:{int(start_time % 60):02},{int((start_time % 1) * 1000):03}"
        end_srt = f"{int(end_time // 3600):02}:{int((end_time % 3600) // 60):02}:{int(end_time % 60):02},{int((end_time % 1) * 1000):03}"
        
        # Append to SRT string
        srt += f"{id}\n{start_srt} --> {end_srt}\n{text}\n\n"
        
        # Update last_id and last_end_time
        last_id = id
        last_end_time = end_time
    
    return srt
