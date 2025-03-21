from config import Config
from pydub import AudioSegment
import logging
import io
import os
from datetime import datetime
import subprocess
import tempfile
import struct

logger = logging.getLogger(__name__)

# ******************************************** All in memory processing ************************************************
# Extract audio from video
def extract_audio(video_binary, file_type, logger=logger):
    """Extract audio from binary video using pydub, or return the binary if already audio.

    Args:
        video_binary (bytes): Binary content of the file (video or audio).
        file_type (str): File type/extension (e.g., 'mp4', 'mpga').
        logger (logging.Logger): Logger instance for logging.

    Returns:
        bytes: Binary content of the extracted or original audio file.
    """
    try:
        logger.info(f"Processing file type: {file_type}")
        
        video_extensions = {'mp4', 'mpeg', 'mpga', 'm4a', 'webm'}
        
        if file_type not in video_extensions:
            logger.info("File is not a video, returning original binary as audio file")
            return video_binary
        
        # Load video binary as audio using pydub
        video_stream = io.BytesIO(video_binary)
        audio = AudioSegment.from_file(video_stream, format=file_type)
        
        # Convert audio to mp3
        audio_binary = io.BytesIO()
        audio.export(audio_binary, format="mp3")
        
        audio_binary.seek(0)
        logger.info("Audio extracted successfully with pydub")
        
        return audio_binary.read()
    
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return None

def preprocess_audio(audio_binary):
    """Preprocess binary audio file to 16kHz mono FLAC using pydub."""
    try:
        logger.info("Preprocessing audio")
        audio = AudioSegment.from_file(io.BytesIO(audio_binary))
        audio = audio.set_frame_rate(16000).set_channels(1)
        processed_audio_binary = io.BytesIO()
        audio.export(processed_audio_binary, format='flac')
        processed_audio_binary.seek(0)
        logger.info("Audio preprocessing complete")
        return processed_audio_binary.read()
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        raise RuntimeError(f"Audio conversion failed: {e}")

def split_audio_into_chunks(audio_binary, chunk_length=600, overlap=Config.GROQ_OVERLAP_TIME):
    """Split binary audio into chunks with overlap."""
    audio = AudioSegment.from_file(io.BytesIO(audio_binary), format="flac")
    duration = len(audio)
    chunk_ms = chunk_length * 1000
    overlap_ms = overlap * 1000
    chunks = []
    
    for start in range(0, duration, chunk_ms - overlap_ms):
        end = min(start + chunk_ms, duration)
        chunk_audio = audio[start:end]
        chunk_binary = io.BytesIO()
        chunk_audio.export(chunk_binary, format='flac')
        chunk_binary.seek(0)
        chunks.append(chunk_binary)
    
    return chunks


# ******************************************** Using filesystem ************************************************

def generate_new_filename(file_path, new_extension):
    """Generate a new filename with timestamp and specified extension."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    new_filename = f"{base_name}_{timestamp}.{new_extension}"
    return os.path.join(os.path.dirname(file_path), new_filename)

def preprocess_audio_filesystem(file_path, logger=logger):
    """Extract audio from video and preprocess it in one step using ffmpeg."""
    try:
        file_type = file_path.split('.')[-1]
        logger.info(f"Processing file: {file_path} with type: {file_type}")
        
        video_extensions = {'mp4', 'mpeg', 'mpga', 'm4a', 'webm'}
        
        # Generate a new filename for the processed audio
        processed_audio_path = generate_new_filename(file_path, 'flac')
        
        if file_type not in video_extensions:
            logger.info("File is not a video, processing directly as audio")
            command = [
            'ffmpeg', '-i', file_path,                # Input audio file
            '-ar', '16000',                           # Set audio sample rate to 16kHz
            '-ac', '1',                               # Set audio to mono (1 channel)
            '-acodec', 'flac',                        # Output as FLAC codec
            processed_audio_path                  # Output file
            ]
        else:
            # Run ffmpeg to extract audio and preprocess in one step (16kHz mono FLAC)
            command = [
                'ffmpeg', '-i', file_path,               # Input video file
                '-vn',                                   # Disable video recording
                '-ar', '16000',                          # Set audio sample rate to 16kHz
                '-ac', '1',                              # Set audio to mono (1 channel)
                '-acodec', 'flac',                       # Output as FLAC codec
                processed_audio_path                 # Output audio file
            ]
        
        subprocess.run(command, check=True)
        
        logger.info(f"Audio extraction and preprocessing complete: {processed_audio_path}")
        
        # Delete the original video file after processing
        os.remove(file_path)
        logger.info(f"Original file deleted: {file_path}")
        
        return processed_audio_path
    
    except Exception as e:
        logger.error(f"Error extracting and preprocessing audio: {e}")
        return None
    
    
def bytes_to_int(bytes: list) -> int:
    """Convert a list of bytes to an integer."""
    result = 0
    for byte in bytes:
        result = (result << 8) + byte
    return result

def get_flac_duration(filename: str) -> float:
    """Returns the duration of a FLAC file in seconds by reading its metadata."""
    try:
        with open(filename, 'rb') as f:
            if f.read(4) != b'fLaC':
                raise ValueError('File is not a FLAC file')

            while True:
                header = f.read(4)
                if not header:
                    break  # End of file

                meta = struct.unpack('4B', header)  # Read 4 bytes
                block_type = meta[0] & 0x7F  # 0111 1111
                size = bytes_to_int(header[1:4])

                if block_type == 0:  # Metadata Streaminfo block
                    streaminfo_header = f.read(size)
                    unpacked = struct.unpack('2H3p3p8B16p', streaminfo_header)

                    samplerate = bytes_to_int(unpacked[4:7]) >> 4
                    sample_bytes = [(unpacked[7] & 0x0F)] + list(unpacked[8:12])
                    total_samples = bytes_to_int(sample_bytes)

                    return float(total_samples) / samplerate

        logger.error("No Streaminfo block found in FLAC file.")
        return None
    except Exception as e:
        logger.error(f"Error reading FLAC metadata: {e}")
        return None
    
    
def split_audio_into_chunks_filesystem(file_path, chunk_length=600, overlap=Config.GROQ_OVERLAP_TIME):
    """Split audio into chunks with overlap using temporary files, avoiding high memory usage."""
    try:
        
        duration = get_flac_duration(file_path)
        if duration is None:
            logger.error("Cannot estimate duration, splitting failed")
            return None
        
        chunks = []

        # Loop to split the file
        for start in range(0, int(duration), chunk_length - overlap):
            end = min(start + chunk_length, int(duration))

            # Create a temporary file for each chunk
            with tempfile.NamedTemporaryFile(delete=False, suffix='.flac') as temp_chunk_file:
                temp_chunk_filename = temp_chunk_file.name
                
                # Use ffmpeg to extract the chunk directly into the temporary file
                command = [
                    'ffmpeg', '-i', file_path, 
                    '-vn', '-acodec', 'flac', 
                    '-ss', str(start), '-to', str(end),
                    '-y',
                    temp_chunk_filename
                ]
                subprocess.run(command, check=True)
                
                # Append the chunk file path to the list
                chunks.append(temp_chunk_filename)
        
        os.remove(file_path)
        logger.info(f"Original file deleted: {file_path}")
        return chunks

    except Exception as e:
        logger.error(f"Error splitting audio: {e}")
        return None