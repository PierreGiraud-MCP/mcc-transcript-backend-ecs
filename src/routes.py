import json
import os
from src.file_utils import save_transcription
from src.process_audio import (extract_audio, preprocess_audio, split_audio_into_chunks, 
                                preprocess_audio_filesystem, split_audio_into_chunks_filesystem)
from src.merge_transcription import merge_transcriptions
from flask import request, jsonify, send_file, Response, stream_with_context
import time
from app import app
from src.client import (initialize_client, transcribe_openai, transcribe_groq, 
                        Transcribe_WithGroq_SingleChunk, GenerateSRTFromGroq)
from config import (Config, read_log_file) 
import logging
from src.s3Bucket import (check_file_exists, upload_to_s3, delete_file_from_s3, 
                            list_files_in_s3, open_from_s3, generate_presigned_url_GET, 
                            generate_presigned_url_POST, get_all_fileNames_in_s3,
                            download_from_s3, Delete_Old_Files_From_S3)
import requests

logger = logging.getLogger(__name__)

# Global variable to track the last cleanup time
last_cleanup_time = 0

# ******************************************** Test Routes ************************************************
@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/logs')
def logs():
    logs = read_log_file()
    # Directly embed the HTML-formatted logs into the page
    return f"""
    <html>
        <head>
            <title>Application Logs</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f9;
                    color: #333;
                    padding: 20px;
                }}
                .log {{
                    white-space: pre-wrap;
                    font-family: monospace;
                    background-color: #1e1e1e;
                    color: #dcdcdc;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
            </style>
        </head>
        <body>
            <h1>Application Logs</h1>
            <div class="log">{logs}</div>
        </body>
    </html>
    """

@app.route('/api/test/s3')
def do():
    """Test route for S3 in browser"""
    # check if the file exists in file system
    file_name = "NodeJSTuto.mp3"
    file_path = "test/NodeJSTuto.mp3"
    if not os.path.exists(file_path):
        return jsonify({'error': 'not allowed to do this test'}), 404
    
    # test get_all_fileNames_in_s3
    file_names = get_all_fileNames_in_s3(logger)
    
    # test upload_to_s3 with test/NodeJSTuto.mp3
    with open(file_path, 'rb') as file:
        file_content = file.read()
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
    uploadResponse = upload_to_s3(file_content, file_name, file_size, logger)
    
    file_names_after_upload = get_all_fileNames_in_s3(logger)
    
    # test open_from_s3 with NodeJSTuto.mp3
    file_name = "NodeJSTuto.mp3"
    content, file_type = open_from_s3(file_name, logger)
    
    with open("test/ReceivedNoeJSTuto.mp3", 'wb') as file:
        file.write(content['Body'].read())
    
    # test delete_from_s3 with NodeJSTuto.mp3
    file_name = "NodeJSTuto.mp3"
    deleteResponse = delete_file_from_s3(file_name, logger)
    
    file_names_after_delete = get_all_fileNames_in_s3(logger)
    
    # return the results
    return jsonify({
        'file_names': file_names,
        'uploadResponse': uploadResponse,
        'file_names_after_upload': file_names_after_upload,
        'deleteResponse': deleteResponse,
        'file_names_after_delete': file_names_after_delete
    })

@app.route('/api/test/s3/presigned_url_POST')
def test_presigned_url():
    """Test route for generating presigned URL"""
        # check if the file exists in file system
    file_name = "NodeJSTuto.mp3"
    file_path = "test/NodeJSTuto.mp3"
    file_size = os.path.getsize(file_path)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'not allowed to do this test'}), 404
    
    post_url = generate_presigned_url_POST(file_name, file_size, expires_in=60)
    files = {'file': (open(file_path, 'rb'))}
    response = requests.post(post_url['url'],data=post_url['fields'], files=files)
    
    return f"Response: {response.text}"

@app.route('/api/test/s3/presigned_url_GET')
def test_presigned_url_GET():
    """Test route for generating presigned URL"""
    # check if the file exists in file system
    file_name = "NodeJSTuto.mp3"
    file_path = "test/NodeJSTuto.mp3"
    if not os.path.exists(file_path):
        return jsonify({'error': 'not allowed to do this test'}), 404
    
    presigned_url = generate_presigned_url_GET(file_name, expires_in=600)
    return jsonify({'presigned_url': presigned_url})

# ******************************************** progess Routes ************************************************
progress = 0
step = "Starting..."
last_sent_progress = -1
@app.route('/api/progress', methods=['GET'])
def get_progress():
    global progress
    global step
    global last_sent_progress        
    if progress != last_sent_progress:  # Only send if there's an update
        last_sent_progress = progress
        return jsonify({"progress": progress, "step": step}), 200   
    return "", 204  # No content if progress hasn't changed

# ******************************************** Main Routes ************************************************

@app.route('/api/upload', methods=['POST'])
def upload():
    """ Handle file upload """
    global progress
    global step
    progress = 0
    step = "Starting upload..."
    try:
        data = request.get_json()
        filename = data.get('filename')
        filesize = data.get('filesize')
        
        logger.info(f"Received file upload request: {data}")

        progress = 2
        step = "Generating presigned URL..."
        # Generate presigned URL for the file
        presigned_url = generate_presigned_url_POST(filename, filesize, expires_in=10)  # Increase expiration time if needed

        progress = 5
        step = "Uploading the document..."
        logger.info(f"Presigned URL generated: {presigned_url}")
        
        if "already_exists" in presigned_url:
            return jsonify({'presignedUrl': presigned_url}), 201
        
        # Return the presigned URL to the client
        return jsonify({'presignedUrl': presigned_url}), 200
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': 'Upload failed', 'details': str(e)}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    """ Transcribe audio file """
    global progress
    global step
    global last_cleanup_time
    progress = 15
    step = "Document uploaded"
    client = initialize_client()
    try:
        data = request.get_json()
        filename = data.get('filename')
        language = data.get('language')
        translation_language = data.get('translation_language')

        if not filename:
            return jsonify({'error': 'No filename provided'}), 400
        if not language:
            return jsonify({'error': 'No language selected'}), 400
        if not translation_language:
            return jsonify({'error': 'No translation language selected'}), 400
        
        if translation_language == "en":
            language = "en"

        file_path = filename # TODO add config folder once
        
        step = "Checking if the document is correctly uploaded..."
        # check for file path in s3 bucket
        fileExist, _ = check_file_exists(file_path, 1000)
        
        if not fileExist:
            logger.error(f"File not found at path: {file_path}")
            return jsonify({'error': 'File not found'}), 404
        
        if Config.USE_FILE_SYSTEM == "false":
            # Get File from s3 bucket
            content, file_type = open_from_s3(file_path, logger)

            progress = 20
            step = "Extracting audio..."
            audio_content = extract_audio(content, file_type, logger)
            if audio_content is None:
                logger.error("Failed to extract audio")
                return jsonify({'error': 'Failed to extract audio'}), 500

            progress = 30
            step = "Preprocessing audio..."
            processed_audio = preprocess_audio(audio_content)
            progress = 40
            step = "Splitting audio into chunks..."

            chunks = split_audio_into_chunks(processed_audio)

            results = []
            total_transcription_time = 0

            progress = 45
            step = "Transcribing audio..."
            for i, chunk in enumerate(chunks):
                progress = 45 + (i / len(chunks)) * 35
                step = f"Transcribing chunk {i + 1} of {len(chunks)}"
                
                logger.info(f"Transcribing chunk {i + 1} of {len(chunks)}")
                result, chunk_time = Transcribe_WithGroq_SingleChunk(client, chunk, i + 1, len(chunks), language)
                total_transcription_time += chunk_time
                results.append((result, i * (600 - 10) * 1000))
                
        elif Config.USE_FILE_SYSTEM == "true":
            progress = 20
            step = "Preprocessing audio..."
            local_file_path = download_from_s3(file_path, logger)
            local_processed_file_path = preprocess_audio_filesystem(local_file_path, logger)
            
            progress = 40
            step = "Splitting audio into chunks..."
            local_chunks = split_audio_into_chunks_filesystem(local_processed_file_path)

            results = []
            total_transcription_time = 0
            progress = 45
            step = "Transcribing audio..."

            for i, chunk_file in enumerate(local_chunks):
                progress = 45 + (i / len(local_chunks)) * 35
                step = f"Transcribing chunk {i + 1} of {len(local_chunks)}"
                
                logger.info(f"Transcribing chunk {i + 1} of {len(local_chunks)}")
                
                # Open the temporary chunk file
                with open(chunk_file, 'rb') as chunk:
                    result, chunk_time = Transcribe_WithGroq_SingleChunk(client, chunk, i + 1, len(local_chunks), language)
                
                total_transcription_time += chunk_time
                results.append((result, i * (600 - 10) * 1000))
                
                # Clean up the temporary chunk file
                os.remove(chunk_file)
            
        else:
            logger.error(f"File system configuration error with USE_FILE_SYSTEM: {Config.USE_FILE_SYSTEM}")
            return jsonify({'error': 'File system configuration error'}), 500
        
        

        progress = 80
        step = "Merging transcriptions..."
        # Delete audio_files from s3
        delete_file_from_s3(file_path, logger)
        
        final_result = merge_transcriptions(results)
        
        progress = 90
        step = "Generating files..."
        srt = GenerateSRTFromGroq(final_result['segments'], logger)
        time_stamp, txt_path, docx_path, srt_path = save_transcription(final_result['text'], filename, srt, logger)
        
        progress = 100
        step = "Transcription complete !"

        # cleanup the file from s3 if did not already do it within the last hour
        current_time = time.time()
        if current_time - last_cleanup_time > 3600:  # 3600 seconds = 1 hour
            Delete_Old_Files_From_S3()
            last_cleanup_time = current_time  

        return jsonify({
            'success': True,
            'filename': filename,
            'transcription': final_result['text'],
            'timestamp': time_stamp,
            'txt': os.path.basename(txt_path),
            'word_doc': os.path.basename(docx_path),
            'srt': os.path.basename(srt_path) if srt_path else None
        }), 200
    except Exception as e:
        logger.error(f"Error during transcription of {filename}: {e}")
        return jsonify({'error': 'Transcription failed', 'details': str(e)}), 500
    finally:
        # Clean up any leftover files in VIDEO_FOLDER
        logger.info("Cleaning up leftover files in VIDEO_FOLDER")
        if Config.USE_FILE_SYSTEM == "true" and os.path.exists(Config.VIDEO_FOLDER):
            for file in os.listdir(Config.VIDEO_FOLDER):
                file_path = os.path.join(Config.VIDEO_FOLDER, file)
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted leftover file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to delete leftover file {file_path}: {cleanup_error}")

@app.route('/api/download/<filename>', methods=['GET'])
def download(filename):
    """Download document"""
    try:
        # Generate presigned URL for the file
        logger.info(f"Trying to generate presigned URL for download: {filename}")
        presigned_url = generate_presigned_url_GET(filename, expires_in=60)
        return jsonify({'presignedUrl': presigned_url})
    except Exception as e:
        logger.error(f"Error generating presigned URL for download: {str(e)}")
        return jsonify({'error': 'Download failed', 'details': str(e)}), 500

