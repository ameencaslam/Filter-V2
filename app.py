"""
Image Filter Tool - Backend Server

This Flask application serves as the backend for an image filtering tool.
It manages image batches, tracks their status, and handles batch operations
through a CSV file.

Configuration:
    - BATCH_SIZE: Maximum number of images per batch
    - CSV_PATH: Path to the CSV file storing image statuses
    - IMAGE_DIR: Directory containing the images
    - ALLOWED_EXTENSIONS: Set of allowed image file extensions
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd
import os
from pathlib import Path
import logging

# Set up logging for debugging and error tracking
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Application Configuration
BATCH_SIZE = 72  # Default number of images per batch
CSV_PATH = 'images.csv'  # File to store image statuses
IMAGE_DIR = 'nutshell30k'  # Directory containing images
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}  # Supported image formats

def initialize_csv():
    """
    Initialize or verify the CSV file that tracks image statuses.
    Creates a new CSV if it doesn't exist, scanning the image directory
    and setting all images to 'original' status.
    """
    if not os.path.exists(CSV_PATH):
        try:
            df = pd.DataFrame(columns=['filename', 'status'])
            
            if not os.path.exists(IMAGE_DIR):
                logger.error(f"Directory {IMAGE_DIR} not found!")
                return
            
            # Get list of valid image files
            images = [f for f in os.listdir(IMAGE_DIR) 
                     if Path(f).suffix.lower() in ALLOWED_EXTENSIONS]
            
            if not images:
                logger.warning(f"No images found in {IMAGE_DIR}")
                return
                
            # Create DataFrame with all images set to 'original' status
            df = pd.DataFrame({
                'filename': images,
                'status': ['original'] * len(images)
            })
            
            df.to_csv(CSV_PATH, index=False)
            logger.info(f"Created new CSV file with {len(images)} images")
        except Exception as e:
            logger.error(f"Error initializing CSV: {str(e)}")
            raise

def get_batch():
    """
    Retrieve the next batch of unprocessed ('original') images.
    
    Returns:
        tuple: (list of image filenames, dictionary of statistics)
        Statistics include counts of original, good, and bad images.
    """
    initialize_csv()
    
    try:
        df = pd.read_csv(CSV_PATH)
        original_images = df[df['status'] == 'original']['filename'].tolist()
        
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

# Route Handlers
@app.route('/')
def index():
    """Serve the main application page."""
    initialize_csv()
    return render_template('index.html')

@app.route('/get_batch')
def get_next_batch():
    """
    API endpoint to get the next batch of images.
    Returns JSON with image paths and current statistics.
    """
    batch, stats = get_batch()
    return jsonify({
        'images': [f'{IMAGE_DIR}/{img}'.replace('\\', '/') for img in batch],
        'stats': stats
    })

@app.route('/<path:filename>')
def serve_image(filename):
    """
    Serve individual image files from the image directory.
    Handles proper path resolution and security checks.
    """
    logger.debug(f"Attempting to serve image: {filename}")
    
    base_dir = os.path.abspath(os.path.dirname(__file__))
    directory = os.path.dirname(os.path.join(base_dir, filename))
    file_name = os.path.basename(filename)
    
    if os.path.exists(os.path.join(directory, file_name)):
        return send_from_directory(directory, file_name)
    return "File not found", 404

@app.route('/update_batch', methods=['POST'])
def update_batch():
    """
    API endpoint to update image statuses for a batch.
    Accepts lists of 'good' and 'bad' images and updates their status in the CSV.
    """
    data = request.json
    good_images = data.get('good_images', [])
    bad_images = data.get('bad_images', [])
    
    df = pd.read_csv(CSV_PATH)
    df.loc[df['filename'].isin(good_images), 'status'] = 'good'
    df.loc[df['filename'].isin(bad_images), 'status'] = 'bad'
    df.to_csv(CSV_PATH, index=False)
    
    batch, stats = get_batch()
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/undo_last_batch', methods=['POST'])
def undo_last_batch():
    """
    API endpoint to undo the last batch submission.
    Resets the status of the specified images back to 'original'.
    """
    data = request.json
    previous_batch = data.get('previous_batch', [])
    
    df = pd.read_csv(CSV_PATH)
    df.loc[df['filename'].isin(previous_batch), 'status'] = 'original'
    df.to_csv(CSV_PATH, index=False)
    
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
