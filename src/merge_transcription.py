from config import Config
import re

def merge_transcriptions(results):
    """Merge transcription chunks and handle overlaps."""
    final_segments = []
    processed_chunks = []
    
    # harmonize id and timestamp between chunks
    firstChunkID = 0
    paddedTimeForNextChunk = 0.0
    
    for i, (chunk, _) in enumerate(results):
        segments = chunk.segments  # Access the segments attribute of the Transcription object
        if i < len(results):
            if i < len(results) - 1:
                next_start = results[i + 1][1]
            else:
                next_start = None
            current_segments = []
            overlap_segments = []
            
            for segment in segments:
                segment.update({
                    'id': segment['id'] + firstChunkID, # harmonize IDs
                    'start': segment['start'] + paddedTimeForNextChunk, # harmonize start time
                    'end': segment['end'] + paddedTimeForNextChunk}) # hamonize end time
                if next_start and segment['end'] * 1000 > next_start:
                    overlap_segments.append(segment)
                else:
                    current_segments.append(segment)
            
            if overlap_segments:
                merged_overlap = overlap_segments[0].copy()
                firstChunkID = merged_overlap['id'] + 1 # get the first ID for next chunk
                paddedTimeForNextChunk = overlap_segments[-1]['end'] - Config.GROQ_OVERLAP_TIME # time of the last segment
                merged_overlap.update({
                    'text': ' '.join(s['text'] for s in overlap_segments),
                    'end': overlap_segments[-1]['end'] # time of the last segment
                })
                current_segments.append(merged_overlap)
            
            processed_chunks.append(current_segments)
        else:
            processed_chunks.append(segments)
    
    # Harmonize start and end times between chunks
        
    for i in range(len(processed_chunks) - 1):
        final_segments.extend(processed_chunks[i][:-1]) # append chunk segments except the last one
        last_segment = processed_chunks[i][-1] # last segment
        first_segment = processed_chunks[i + 1][0] # first segment of next chunk
        merged_text = find_longest_common_sequence([last_segment['text'], first_segment['text']])
        merged_segment = last_segment.copy()
        merged_segment.update({
            'text': merged_text,
            'end': first_segment['end']
        })
        final_segments.append(merged_segment)
    
    if processed_chunks:
        final_segments.extend(processed_chunks[-1])
    
    final_text = ' \n'.join(segment['text'] for segment in final_segments)
    
    return {
        "text": final_text,
        "segments": final_segments
    }

def find_longest_common_sequence(sequences):
    """Find the optimal alignment between sequences with longest common sequence and sliding window matching."""
    if not sequences:
        return ""
    
    sequences = [[word for word in re.split(r'(\s+\w+)', seq) if word] for seq in sequences]
    left_sequence = sequences[0]
    left_length = len(left_sequence)
    total_sequence = []
    
    for right_sequence in sequences[1:]:
        max_matching = 0.0
        right_length = len(right_sequence)
        max_indices = (left_length, left_length, 0, 0)
        
        for i in range(1, left_length + right_length + 1):
            eps = float(i) / 10000.0
            left_start = max(0, left_length - i)
            left_stop = min(left_length, left_length + right_length - i)
            left = left_sequence[left_start:left_stop]
            right_start = max(0, i - left_length)
            right_stop = min(right_length, i)
            right = right_sequence[right_start:right_stop]
            
            if len(left) != len(right):
                raise RuntimeError("Mismatched subsequences detected during transcript merging.")
            
            matches = sum(a == b for a, b in zip(left, right))
            matching = matches / float(i) + eps
            
            if matches > 1 and matching > max_matching:
                max_matching = matching
                max_indices = (left_start, left_stop, right_start, right_stop)
        
        left_start, left_stop, right_start, right_stop = max_indices
        left_mid = (left_stop + left_start) // 2
        right_mid = (right_stop + right_start) // 2
        total_sequence.extend(left_sequence[:left_mid])
        left_sequence = right_sequence[right_mid:]
        left_length = len(left_sequence)
    
    total_sequence.extend(left_sequence)
    return ''.join(total_sequence)