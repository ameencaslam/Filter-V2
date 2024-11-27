from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd
import os
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BATCH_SIZE = 72
CSV_PATH = 'images.csv'

# Replace before_first_request with a function that runs at startup
def check_paths():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    images_dir = os.path.join(base_dir, 'nutshell30k')
    
    logger.debug(f"Base directory: {base_dir}")
    logger.debug(f"Images directory: {images_dir}")
    logger.debug(f"Images directory exists: {os.path.exists(images_dir)}")

# Call check_paths at startup
check_paths()

def initialize_csv():
    if not os.path.exists(CSV_PATH):
        # Get all image files from the folder
        images_dir = 'nutshell30k' #Replace with your dataset directory
        try:
            # Create empty DataFrame first
            df = pd.DataFrame(columns=['filename', 'status'])
            
            # Check if directory exists
            if not os.path.exists(images_dir):
                logger.error(f"Directory {images_dir} not found!")
                return
            
            # Get list of images
            images = [f for f in os.listdir(images_dir) 
                     if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            if not images:
                logger.warning(f"No images found in {images_dir}")
                return
                
            # Create DataFrame with images
            df = pd.DataFrame({
                'filename': images,
                'status': ['original'] * len(images)
            })
            
            # Save to CSV directly (no need for makedirs since it's in current directory)
            df.to_csv(CSV_PATH, index=False)
            logger.info(f"Created new CSV file with {len(images)} images")
        except Exception as e:
            logger.error(f"Error initializing CSV: {str(e)}")
            raise

def get_batch():
    # Initialize CSV if it doesn't exist
    initialize_csv()
    
    try:
        df = pd.read_csv(CSV_PATH)
        original_images = df[df['status'] == 'original']['filename'].tolist()
        
        # Get the requested batch size from the query parameter, default to BATCH_SIZE
        requested_size = request.args.get('size', BATCH_SIZE, type=int)
        batch = original_images[:requested_size]
        
        stats = {
            'original': len(df[df['status'] == 'original']),
            'good': len(df[df['status'] == 'good']),
            'bad': len(df[df['status'] == 'bad'])
        }
        
        return batch, stats
    except Exception as e:
        logger.error(f"Error getting batch: {str(e)}")
        return [], {'original': 0, 'good': 0, 'bad': 0}

@app.route('/')
def index():
    # Initialize CSV if it doesn't exist
    initialize_csv()
    return render_template('index.html')

@app.route('/get_batch')
def get_next_batch():
    batch, stats = get_batch()
    # Use forward slashes for URLs even on Windows
    return jsonify({
        'images': [f'nutshell30k/{img}'.replace('\\', '/') for img in batch],
        'stats': stats
    })

@app.route('/update_batch', methods=['POST'])
def update_batch():
    data = request.json
    good_images = data.get('good_images', [])
    bad_images = data.get('bad_images', [])
    
    df = pd.read_csv(CSV_PATH)
    
    # Update statuses
    df.loc[df['filename'].isin(good_images), 'status'] = 'good'
    df.loc[df['filename'].isin(bad_images), 'status'] = 'bad'
    
    df.to_csv(CSV_PATH, index=False)
    
    # Get next batch and stats
    batch, stats = get_batch()
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/<path:filename>')
def serve_image(filename):
    logger.debug(f"Attempting to serve image: {filename}")
    
    # Get the absolute path to your project directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Construct the full path
    full_path = os.path.join(base_dir, filename)
    logger.debug(f"Full path: {full_path}")
    
    # Get directory and filename
    directory = os.path.dirname(full_path)
    file_name = os.path.basename(full_path)
    
    if os.path.exists(full_path):
        logger.debug(f"File found: {full_path}")
        return send_from_directory(directory, file_name)
    else:
        logger.error(f"File not found: {full_path}")
        return "File not found", 404

@app.route('/undo_last_batch', methods=['POST'])
def undo_last_batch():
    data = request.json
    previous_batch = data.get('previous_batch', [])
    bad_images = data.get('bad_images', [])
    
    df = pd.read_csv(CSV_PATH)
    
    # Reset the status of the previous batch images back to 'original'
    df.loc[df['filename'].isin(previous_batch), 'status'] = 'original'
    
    # Save changes
    df.to_csv(CSV_PATH, index=False)
    
    # Get updated stats
    stats = {
        'original': len(df[df['status'] == 'original']),
        'good': len(df[df['status'] == 'good']),
        'bad': len(df[df['status'] == 'bad'])
    }
    
    return jsonify({
        'success': True,
        'stats': stats
    })

if __name__ == '__main__':
    app.run(debug=True) 
