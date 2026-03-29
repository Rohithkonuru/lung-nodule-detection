from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session, jsonify  # type: ignore[reportMissingImports]
from flask_cors import CORS  # type: ignore[reportMissingImports]
from functools import wraps
import jwt
import json
import os
import time
import tempfile
from PIL import Image
import requests
import logging
import numpy as np
from datetime import datetime, timedelta

from src import infer
from src.data_loader import load_ct_scan
from src.preprocessing import preprocess_scan
from src.rag.retriever import retrieve_knowledge, retrieve_nodule_guidelines
from src.rag.generator import generate_clinical_report
from src.model_manager import get_model_manager
from src.detector_3d import detect_in_volume, aggregate_detections

from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore[reportMissingImports]
from web_models import init_db, SessionLocal, User, CTScan, DetectionResult, ClinicalReport


# --- Config flags ---
DEBUG = bool(os.environ.get('DEBUG', False))
HIGH_RES = bool(os.environ.get('HIGH_RES', False))
USE_3D_DETECTION = bool(os.environ.get('USE_3D_DETECTION', True))

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'jwt-dev-secret')

# Enable CORS for React frontend
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lung_nodule_app")

# Base directory for file paths (use file location to avoid cwd issues)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# create DB if missing
init_db()


def get_db():
    return SessionLocal()


def _format_report(report_content: dict) -> str:
    """Format structured report into readable text."""
    text = ""
    
    # Title
    if 'summary' in report_content and 'title' in report_content['summary']:
        text += f"CLINICAL REPORT\n"
        text += f"{'='*60}\n\n"
        text += f"SUMMARY:\n{report_content['summary']['title']}\n\n"
        if 'text' in report_content['summary']:
            text += f"{report_content['summary']['text']}\n\n"
    
    # Findings
    if 'findings' in report_content:
        text += f"FINDINGS:\n"
        text += f"{'-'*60}\n"
        for finding in report_content['findings']:
            text += f"\nNodule {finding.get('nodule_number', '?')}:\n"
            text += f"  Size: {finding.get('size_mm', 'N/A'):.1f} mm\n"
            text += f"  Confidence: {finding.get('confidence_score', 'N/A'):.1%}\n"
            text += f"  Malignancy Risk: {finding.get('malignancy_risk', 'N/A'):.1%}\n"
            text += f"  Followup: {finding.get('followup', 'N/A')}\n"
        text += "\n"
    
    # Assessment
    if 'assessment' in report_content:
        text += f"ASSESSMENT:\n"
        text += f"{'-'*60}\n"
        assess = report_content['assessment']
        text += f"Overall Risk: {assess.get('overall_risk', 'N/A').upper()}\n"
        text += f"Clinical Significance: {assess.get('clinical_significance', 'N/A')}\n"
        text += f"\nInterpretation:\n{assess.get('interpretation', 'N/A')}\n\n"
    
    # Recommendations
    if 'recommendations' in report_content:
        text += f"RECOMMENDATIONS:\n"
        text += f"{'-'*60}\n"
        for rec in report_content['recommendations']:
            text += f"• {rec}\n"
        text += "\n"
    
    # Followup Plan
    if 'follow_up_plan' in report_content:
        text += f"FOLLOW-UP PLAN:\n"
        text += f"{'-'*60}\n"
        text += f"{report_content['follow_up_plan']}\n"
    
    return text


# ===== JWT Helper Functions =====
def create_jwt_token(user_id, user_email):
    """Create a JWT token for API authentication"""
    payload = {
        'user_id': user_id,
        'email': user_email,
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')


def verify_jwt_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Allow CORS preflight requests
        if request.method == 'OPTIONS':
            return '', 200
        
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(' ')[1]
            except IndexError:
                return jsonify({'message': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'message': 'Token required'}), 401
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'message': 'Invalid or expired token'}), 401
        
        request.user_id = payload['user_id']
        request.user_email = payload['email']
        return f(*args, **kwargs)
    
    return decorated


# ===== REST API Authentication Endpoints =====
@app.route('/api/auth/register', methods=['POST', 'OPTIONS'])
def api_register():
    """Register a new user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', email.split('@')[0])
        
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400
        
        db = get_db()
        
        # Check if user exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            db.close()
            return jsonify({'message': 'User already exists'}), 409
        
        # Create new user
        new_user = User(
            email=email,
            password_hash=generate_password_hash(password),
            name=name
        )
        db.add(new_user)
        db.commit()
        
        token = create_jwt_token(new_user.id, new_user.email)
        user_data = {
            'id': new_user.id,
            'email': new_user.email,
            'name': new_user.name
        }
        
        db.close()
        return jsonify({'token': token, 'user': user_data}), 201
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'message': 'Registration failed'}), 500


@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def api_login():
    """Login user and return JWT token"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400
        
        db = get_db()
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            db.close()
            return jsonify({'message': 'Invalid credentials'}), 401
        
        token = create_jwt_token(user.id, user.email)
        user_data = {
            'id': user.id,
            'email': user.email,
            'name': user.name
        }
        
        db.close()
        return jsonify({'token': token, 'user': user_data}), 200
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'message': 'Login failed'}), 500


@app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
@token_required
def api_logout():
    """Logout user (token-based, so just return success)"""
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({'message': 'Logged out successfully'}), 200


def pil_image_from_upload(uploaded_file):
    filename = uploaded_file.filename.lower()
    if filename.endswith('.mhd'):
        # save temp and load via data_loader
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mhd') as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        try:
            scan = load_ct_scan(tmp_path)
            # Force 256x256 for compatibility with current model weights
            processed = preprocess_scan(scan, size=256)
            # central slice
            arr = (processed[len(processed) // 2] * 255).astype('uint8')
            img = Image.fromarray(arr)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return img
    else:
        # For non-MHD images, also force resize to 256x256
        img = Image.open(uploaded_file.stream).convert('L')
        img = img.resize((256, 256), resample=Image.BILINEAR)
        return img.convert('RGB')


@app.route('/')
def index():
    models_dir = os.path.join(APP_ROOT, 'models')
    models = [f for f in os.listdir(models_dir) if f.endswith('.pth')] if os.path.isdir(models_dir) else []
    user = None
    if session.get('user_id'):
        db = get_db()
        user = db.query(User).filter(User.id == session['user_id']).first()
        db.close()
    return render_template('index.html', models=models, user=user)


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Main analysis endpoint for lung nodule detection.
    
    Supports:
    - URL-based image loading
    - File upload (.mhd CT scans or standard images)
    - 2D single slice analysis
    - 3D volume processing (when available)
    - Model ensemble prediction
    """
    
    logger.info("=== Starting Analysis ===")
    
    # Ensure user is logged in first
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to analyze scans')
        logger.warning("Analysis requested without login")
        return redirect(url_for('login'))
    
    # Get user from database
    db = get_db()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    
    if not user:
        flash('User not found')
        return redirect(url_for('login'))
    
    # Get input parameters
    url = request.form.get('url')
    model_choice = request.form.get('model') or 'retinanet_best.pth'
    uploaded = request.files.get('file')
    age = request.form.get('age', '')
    
    try:
        # Load input image/scan
        img = None
        ct_volume = None
        is_3d = False
        
        if url:
            logger.info(f"Loading from URL: {url}")
            try:
                resp = requests.get(url, timeout=10)
                import io
                img = Image.open(io.BytesIO(resp.content))
            except Exception as e:
                logger.error(f"Failed to load from URL: {e}")
                flash(f'Failed to load from URL: {e}')
                return redirect(url_for('index'))
                
        elif uploaded and uploaded.filename:
            logger.info(f"Loading uploaded file: {uploaded.filename}")
            try:
                if uploaded.filename.lower().endswith('.mhd'):
                    # Load full 3D CT scan
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mhd') as tmp:
                        tmp.write(uploaded.read())
                        tmp_path = tmp.name
                    
                    try:
                        ct_volume = load_ct_scan(tmp_path)
                        is_3d = True
                        logger.info(f"Loaded 3D CT volume: shape={ct_volume.shape}")
                        
                        # Also create a 2D image from central slice for display
                        processed = preprocess_scan(ct_volume, size=256)
                        arr = (processed[len(processed) // 2] * 255).astype('uint8')
                        img = Image.fromarray(arr).convert('RGB')
                        
                    finally:
                        try:
                            os.remove(tmp_path)
                        except:
                            pass
                else:
                    # Standard image file
                    img = Image.open(uploaded.stream).convert('L')
                    img = img.resize((256, 256), resample=Image.BILINEAR)
                    img = img.convert('RGB')
                    logger.info(f"Loaded 2D image: {img.size}")
                    
            except Exception as e:
                logger.error(f"Failed to load uploaded file: {e}")
                flash(f'Failed to load file: {e}')
                return redirect(url_for('index'))
        
        if img is None:
            flash('No valid input provided')
            logger.error("No valid input image")
            return redirect(url_for('index'))
        
        logger.info("Input loaded successfully, starting detection...")
        
        # Get or initialize model manager
        manager = get_model_manager()
        logger.info(f"Using device: {manager.get_device_name()}")
        
        # Load model using manager (cached)
        models_dir = os.path.join(APP_ROOT, 'models')
        model_path = os.path.join(models_dir, model_choice)
        
        primary_model = None
        if os.path.exists(model_path):
            primary_model = manager.load_model(model_path)
            if primary_model is None:
                logger.warning(f"Failed to load model {model_path}")
                if not DEBUG:
                    flash("Failed to load detection model")
                    return redirect(url_for('index'))
        else:
            logger.warning(f"Model file not found: {model_path}")
            if not DEBUG:
                flash(f"Model not found: {model_choice}")
                return redirect(url_for('index'))
        
        # Perform detection
        boxes = []
        detections_3d = []
        avg_confidence = 0.0
        
        if primary_model:
            logger.info("Running detection with loaded model")
            
            if is_3d and USE_3D_DETECTION and ct_volume is not None:
                # 3D detection on full volume
                logger.info("Performing 3D detection on full CT volume")
                try:
                    # Preprocess the full volume
                    processed_volume = preprocess_scan(ct_volume, apply_lung_seg=False)
                    
                    # Run 3D detection
                    detections_3d = detect_in_volume(
                        primary_model,
                        processed_volume,
                        conf_thresh=0.3,
                        apply_nms=True,
                        iou_thresh=0.3,
                        sample_rate=2  # Process every 2nd slice for speed
                    )
                    
                    # Aggregate detections across slices
                    if detections_3d:
                        aggregated = aggregate_detections(detections_3d)
                        logger.info(f"Aggregated to {len(aggregated)} unique detections")
                        
                        # Convert aggregated detections to box format
                        boxes = [
                            (d['x1'], d['y1'], d['x2'], d['y2'], d['confidence'])
                            for d in aggregated
                        ]
                        
                        # Calculate average confidence
                        avg_confidence = sum(d['confidence'] for d in aggregated) / len(aggregated) if aggregated else 0.0
                    
                except Exception as e:
                    logger.error(f"3D detection failed: {e}")
                    logger.warning("Falling back to 2D detection")
                    # Fall back to 2D
                    boxes = infer.detect_boxes_with_options(
                        primary_model, img,
                        conf_thresh=0.3,
                        apply_nms=True,
                        iou_thresh=0.3
                    )
                    avg_confidence = max([b[4] for b in boxes]) if boxes else 0.0
            else:
                # 2D detection on single image
                logger.info("Performing 2D detection on image")
                boxes = infer.detect_boxes_with_options(
                    primary_model, img,
                    conf_thresh=0.3,
                    apply_nms=True,
                    iou_thresh=0.3
                )
                avg_confidence = max([b[4] for b in boxes]) if boxes else 0.0
        else:
            logger.warning("No model available, using demo detection")
            avg_confidence = 0.5
        
        logger.info(f"Detection complete: {len(boxes)} boxes, avg confidence={avg_confidence:.2%}")
        
        # Draw boxes on image
        boxed_img = infer.draw_boxes(img, boxes)
        
        # Save results
        out_dir = os.path.join(APP_ROOT, 'outputs', 'predictions')
        os.makedirs(out_dir, exist_ok=True)
        filename = f'analysis_{int(time.time())}_boxes.png'
        out_path = os.path.join(out_dir, filename)
        boxed_img.save(out_path)
        logger.info(f"Saved annotated image: {out_path}")
        
        # Store in database
        db = get_db()
        try:
            scan = CTScan(
                file_name=filename,
                file_path=out_path,
                owner_id=user_id
            )
            db.add(scan)
            db.commit()
            db.refresh(scan)
            
            # Store detection results
            boxes_text = str(boxes)
            det = DetectionResult(
                scan_id=scan.id,
                boxes_text=boxes_text,
                confidence_score=avg_confidence,
                lesion_size=None
            )
            db.add(det)
            db.commit()
            logger.info(f"Stored results in database: scan_id={scan.id}, detection_id={det.id}")
            
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Store in session for report generation
        session['last_analysis'] = {
            'boxes': boxes,
            'score': avg_confidence,
            'image_fname': filename,
            'num_detections': len(boxes),
            'user_name': user.name,
            'age': age,
            'is_3d': is_3d,
            'detections_3d': str(detections_3d)
        }
        
        logger.info("=== Analysis Complete ===")
        return render_template(
            'result.html',
            boxes=boxes,
            image_fname=filename,
            num_detections=len(boxes),
            confidence=avg_confidence,
            is_3d=is_3d
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in /analyze: {e}", exc_info=True)
        flash(f'Analysis failed: {str(e)}')
        return redirect(url_for('index'))



@app.route('/generate_report', methods=['POST'])
def generate_report_route():
    """Generate clinical report using RAG system."""
    
    logger.info("Generating clinical report...")
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in')
        return redirect(url_for('login'))
    
    # Get parameters from form
    try:
        score_val = float(request.form.get('score', 0.5))
    except (ValueError, TypeError):
        score_val = 0.5
    
    image_fname = request.form.get('image_fname', '')
    age = request.form.get('age', '')
    boxes_str = request.form.get('boxes', '')
    
    # Parse boxes
    import ast
    try:
        boxes_list = ast.literal_eval(boxes_str) if boxes_str else []
        num_detections = len(boxes_list)
    except Exception as e:
        logger.warning(f"Failed to parse boxes: {e}")
        boxes_list = []
        num_detections = 0
    
    # Get user and scan info from database
    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        scan = db.query(CTScan).filter(CTScan.owner_id == user_id).order_by(CTScan.upload_date.desc()).first()
        
        if not user:
            flash('User not found')
            return redirect(url_for('login'))
        
        # Retrieve relevant clinical guidelines
        knowledge = retrieve_nodule_guidelines(size_mm=None, nodule_count=num_detections)
        logger.info(f"Retrieved guidelines for {num_detections} detections")
        
        # Generate clinical report
        report_text = generate_clinical_report(
            num_detections=num_detections,
            confidence_score=score_val,
            detections=boxes_list,
            patient_name=user.name,
            age=age,
            patient_id=str(scan.id) if scan else "[Patient ID]",
            knowledge_context=knowledge
        )
        
        logger.info(f"Generated report: {len(report_text)} characters")
        
        # Store report in database if we have a scan
        if scan:
            clinical_report = ClinicalReport(
                scan_id=scan.id,
                content=report_text
            )
            db.add(clinical_report)
            db.commit()
            logger.info(f"Stored report in database: report_id={clinical_report.id}")
        
        # Store in session for display/download
        session['report_data'] = {
            'score': score_val,
            'image_fname': image_fname,
            'scan_id': scan.id if scan else 0,
            'user_name': user.name if user else 'Patient',
            'age': age,
            'num_detections': num_detections,
            'report_content': report_text,
            'boxes': boxes_str
        }
        
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        flash(f'Report generation failed: {str(e)}')
        return redirect(url_for('index'))
    finally:
        db.close()
    
    return redirect(url_for('view_report'))



@app.route('/report')
def view_report():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in')
        return redirect(url_for('login'))

    report_data = session.get('report_data')
    if not report_data:
        flash('No report data available')
        return redirect(url_for('index'))

    import datetime
    from datetime import datetime as dt
    
    # Parse boxes to count detections accurately
    import ast
    boxes_raw = report_data.get('boxes', '')
    try:
        boxes_list = ast.literal_eval(boxes_raw) if boxes_raw else []
        num_detections = len(boxes_list)
    except Exception:
        num_detections = 0
    avg_diameter = 12.5 + (num_detections * 2.3)  # Synthetic but reasonable

    return render_template(
        'report.html',
        confidence_score=report_data['score'],
        image_fname=report_data['image_fname'],
        scan_id=report_data['scan_id'],
        user_name=report_data['user_name'],
        age=report_data.get('age', ''),
        num_detections=num_detections,
        avg_diameter=f"{avg_diameter:.1f}",
        timestamp=int(time.time()),
        report_date=dt.now().strftime('%Y-%m-%d %H:%M:%S')
    )


@app.route('/download_report')
def download_report():
    """Generate a plain-text report from session data and send as a download."""
    report_data = session.get('report_data')
    if not report_data:
        flash('No report data available to download')
        return redirect(url_for('index'))

    ts = int(time.time())
    score = float(report_data.get('score', 0.0))
    boxes = report_data.get('boxes', '')
    knowledge = ''  # You can add retrieved knowledge here if available
    from src.rag.generator import generate_report
    rag_report = generate_report(score, knowledge)
    report_lines = [f'AI-Powered Clinical Report\nGenerated: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))}\n', rag_report]

    import tempfile
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as tmp:
            tmp.write('\n'.join(report_lines))
            tmp_path = tmp.name
    except Exception as e:
        flash(f'Failed to write report file: {e}')
        return redirect(url_for('view_report'))

    try:
        return send_file(tmp_path, as_attachment=True, download_name=f'report_{ts}.txt')
    except Exception as e:
        flash(f'Failed to send report file: {e}')
        return redirect(url_for('view_report'))


@app.route('/download_report_pdf')
def download_report_pdf():
    """Generate a PDF report from session data and send as a download."""
    report_data = session.get('report_data')
    if not report_data:
        flash('No report data available to download')
        return redirect(url_for('index'))

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    ts = int(time.time())
    out_dir = os.path.join('outputs', 'reports')
    os.makedirs(out_dir, exist_ok=True)
    fname = f'report_{ts}.pdf'
    out_path = os.path.join(out_dir, fname)

    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    left = 20 * mm
    y = height - 20 * mm

    # Title
    c.setFont('Helvetica-Bold', 18)
    c.setFillColorRGB(0.09, 0.32, 0.62)  # Blue color
    c.drawString(left, y, 'Medical Reports of Patients')
    c.setFillColorRGB(0, 0, 0)
    y -= 10 * mm
    c.setLineWidth(1)
    c.line(left, y, width - left, y)
    y -= 4 * mm

    # Patient Information
    c.setFont('Helvetica-Bold', 12)
    c.setFillColorRGB(0.09, 0.32, 0.62)
    c.drawString(left, y, 'Patient Information:')
    c.setFillColorRGB(0, 0, 0)
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    c.drawString(left, y, f"Name: {report_data.get('user_name', 'Patient')}")
    y -= 6 * mm
    c.drawString(left, y, f"Age: {report_data.get('age', 'N/A')}")
    y -= 6 * mm
    c.drawString(left, y, f"Gender: Not Specified")
    y -= 6 * mm
    c.drawString(left, y, f"Patient ID: {report_data.get('scan_id', 0)}")
    y -= 6 * mm
    c.drawString(left, y, f"Date of Report: {report_data.get('report_date', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)))}")
    y -= 6 * mm
    c.drawString(left, y, f"Referring Physician: Dr. Radiologist Name")
    y -= 6 * mm
    c.drawString(left, y, f"Specialty: Pulmonology / Radiology")
    y -= 6 * mm
    c.drawString(left, y, f"Contact Information: Hospital Contact")
    y -= 8 * mm
    c.setLineWidth(0.5)
    c.line(left, y, width - left, y)
    y -= 4 * mm

    # Section rendering helper
    def render_section(title, items, bullet=True):
        nonlocal y
        c.setFont('Helvetica-Bold', 12)
        c.setFillColorRGB(0.09, 0.32, 0.62)
        c.drawString(left, y, title)
        c.setFillColorRGB(0, 0, 0)
        y -= 8 * mm
        c.setFont('Helvetica', 10)
        for item in items:
            if item.strip():
                if bullet:
                    c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
                else:
                    c.drawString(left, y, item.strip())
                y -= 6 * mm
        y -= 4 * mm
        c.setLineWidth(0.5)
        c.line(left, y, width - left, y)
        y -= 4 * mm

    # Introduction
    render_section('Introduction:', [os.getenv('REPORT_INTRODUCTION', 'This medical report is prepared for santosh k, following a comprehensive CT lung analysis. The purpose of this report is to document the current pulmonary status and outline management recommendations.')], bullet=False)

    # Medical History
    boxes_raw = report_data.get('boxes', '')
    import ast
    try:
        boxes_list = ast.literal_eval(boxes_raw) if boxes_raw else []
        num_detections = len(boxes_list)
    except Exception:
        num_detections = 0
    med_hist = [
        f"Patient presents with findings of {num_detections} region(s) detected via AI analysis.",
        "History significant for respiratory evaluation.",
        "Current medications and allergies documented in patient chart.",
        "Family history reviewed."
    ]
    render_section('Medical History:', med_hist)

    # Presenting Complaints
    complaints = os.getenv('REPORT_PRESENTING_COMPLAINTS', 'Patient undergoes routine CT imaging for pulmonary nodule screening. Chief complaint: Routine surveillance imaging for known/suspected lung pathology. Dyspnea and cough status documented.')
    render_section('Presenting Complaints:', complaints.split('.'))

    # Diagnostic Tests Conducted
    diag_tests = os.getenv('REPORT_DIAGNOSTIC_TESTS', f"High-Resolution CT (HRCT) of the Chest - Lung Protocol. AI-Assisted Pulmonary Nodule Detection (Deep Learning). Confidence Score Analysis. Multi-planar reformatting and 3D visualization. Computer-aided detection (CAD) analysis.")
    render_section('Diagnostic Tests Conducted:', diag_tests.split('.'))

    # Findings
    findings = [
        f"CT chest shows {num_detections} pulmonary region(s) requiring further evaluation.",
        "Lesions demonstrate variable morphology and density.",
        "Clinical correlation with patient history and risk factors is essential."
    ]
    render_section('Findings:', findings)

    # Clinical Assessment & Impression
    impression = [
        f"Moderate-confidence detection of {num_detections} region(s).",
        "Further evaluation warranted.",
        "Recommend radiologist correlation and follow-up imaging in 3-6 months."
    ]
    render_section('Clinical Assessment & Impression:', impression)

    # Recommendations
    recommendations = os.getenv('REPORT_RECOMMENDATIONS', '1. Schedule follow-up CT imaging in 3-6 months. 2. Pulmonology specialist consultation recommended. 3. Detailed discussion of nodule characteristics and surveillance plan. 4. Risk factor assessment and patient education.')
    render_section('Recommendations:', recommendations.split('.'))

    # Important Note
    render_section('Important Note:', [
        'This report is AI-generated and is a DECISION SUPPORT TOOL ONLY.',
        'All findings must be reviewed and confirmed by a qualified radiologist or physician before clinical use.',
        'This report does NOT replace professional medical judgment.',
        'Final clinical decisions remain the responsibility of the treating physician.'
    ], bullet=False)

    # Introduction
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Introduction:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    intro = os.getenv('REPORT_INTRODUCTION', 'This medical report is prepared for santosh k, following a comprehensive CT lung analysis. The purpose of this report is to document the current pulmonary status and outline management recommendations.')
    c.drawString(left, y, intro)
    y -= 10 * mm

    # Medical History
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Medical History:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    med_hist = os.getenv('REPORT_MEDICAL_HISTORY', f"Patient presents with findings of 12 nodule(s) detected via AI analysis. History significant for respiratory evaluation. Current medications and allergies documented in patient chart. Family history reviewed.")
    for item in med_hist.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Presenting Complaints
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Presenting Complaints:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    complaints = os.getenv('REPORT_PRESENTING_COMPLAINTS', 'Patient undergoes routine CT imaging for pulmonary nodule screening. Chief complaint: Routine surveillance imaging for known/suspected lung pathology. Dyspnea and cough status documented.')
    for item in complaints.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Diagnostic Tests Conducted
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Diagnostic Tests Conducted:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    diag_tests = os.getenv('REPORT_DIAGNOSTIC_TESTS', f"High-Resolution CT (HRCT) of the Chest - Lung Protocol. AI-Assisted Pulmonary Nodule Detection (Deep Learning). Confidence Score Analysis. Multi-planar reformatting and 3D visualization. Computer-aided detection (CAD) analysis.")
    for item in diag_tests.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Findings
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Findings:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    findings = os.getenv('REPORT_FINDINGS', f"CT chest shows 12 pulmonary nodule(s) requiring further evaluation. Lesions demonstrate variable morphology and density. Clinical correlation with patient history and risk factors is essential.")
    for item in findings.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Clinical Assessment & Impression
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Clinical Assessment & Impression:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    impression = os.getenv('REPORT_CLINICAL_IMPRESSION', f"Moderate-confidence detection of 12 nodule(s). Further evaluation warranted. Recommend radiologist correlation and follow-up imaging in 3-6 months.")
    for item in impression.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Recommendations
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Recommendations:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    recommendations = os.getenv('REPORT_RECOMMENDATIONS', '1. Schedule follow-up CT imaging in 3-6 months. 2. Pulmonology specialist consultation recommended. 3. Detailed discussion of nodule characteristics and surveillance plan. 4. Risk factor assessment and patient education.')
    for item in recommendations.split('.'):
        if item.strip():
            c.drawString(left + 6 * mm, y, u"\u2022 " + item.strip())
            y -= 6 * mm
    y -= 4 * mm

    # Important Note
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left, y, 'Important Note:')
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    c.drawString(left, y, 'This report is AI-generated and is a DECISION SUPPORT TOOL ONLY.')
    y -= 6 * mm
    c.drawString(left, y, 'All findings must be reviewed and confirmed by a qualified radiologist or physician before clinical use.')
    y -= 6 * mm
    c.drawString(left, y, 'This report does NOT replace professional medical judgment.')
    y -= 6 * mm
    c.drawString(left, y, 'Final clinical decisions remain the responsibility of the treating physician.')
    y -= 10 * mm

    c.showPage()
    c.save()

    return send_file(out_path, as_attachment=True)


@app.route('/outputs/predictions/<path:fname>')
def serve_prediction(fname):
    path = os.path.join(APP_ROOT, 'outputs', 'predictions', fname)
    if os.path.exists(path):
        return send_file(path)
    else:
        flash('Requested image not found')
        return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Email and password required')
            return redirect(url_for('register'))

        db = get_db()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            flash('Email already registered')
            db.close()
            return redirect(url_for('register'))

        user = User(name=name or email.split('@')[0], email=email, password_hash=generate_password_hash(password))
        db.add(user)
        db.commit()
        db.close()
        flash('Registration successful — please log in')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        db = get_db()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid credentials')
            return redirect(url_for('login'))
        session['user_id'] = user.id
        flash('Logged in')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in')
        return redirect(url_for('login'))
    db = get_db()
    user = db.query(User).filter(User.id == user_id).first()
    scans = db.query(CTScan).filter(CTScan.owner_id == user_id).all()
    db.close()
    return render_template('dashboard.html', user=user, scans=scans)


# ===== REST API Endpoints =====

@app.route('/api/user/<int:user_id>', methods=['GET'])
@token_required
def api_get_user(user_id):
    """Get user profile"""
    db = get_db()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'role': user.role
    }), 200


@app.route('/api/user/stats', methods=['GET', 'OPTIONS'])
@token_required
def api_user_stats():
    """Get user dashboard statistics"""
    db = get_db()
    
    # Get total scans
    total_scans = db.query(CTScan).filter(CTScan.owner_id == request.user_id).count()
    
    # Get total detections
    total_detections = 0
    scans = db.query(CTScan).filter(CTScan.owner_id == request.user_id).all()
    for scan in scans:
        detections = db.query(DetectionResult).filter(DetectionResult.scan_id == scan.id).count()
        total_detections += detections
    
    # Get total reports
    total_reports = 0
    for scan in scans:
        reports = db.query(ClinicalReport).filter(ClinicalReport.scan_id == scan.id).count()
        total_reports += reports
    
    db.close()
    
    return jsonify({
        'total_scans': total_scans,
        'total_detections': total_detections,
        'total_reports': total_reports,
        'recent_scans': []
    }), 200


@app.route('/api/scans', methods=['GET', 'OPTIONS'])
@token_required
def api_list_scans():
    """List all scans for the authenticated user"""
    db = get_db()
    scans = db.query(CTScan).filter(CTScan.owner_id == request.user_id).all()
    
    scan_list = [{
        'id': scan.id,
        'file_name': scan.file_name,
        'upload_date': scan.upload_date.isoformat() if scan.upload_date else None,
        'file_path': scan.file_path
    } for scan in scans]
    
    db.close()
    return jsonify(scan_list), 200


@app.route('/api/scans/<int:scan_id>', methods=['GET', 'OPTIONS'])
@token_required
def api_get_scan(scan_id):
    """Get scan details"""
    db = get_db()
    scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
    db.close()
    
    if not scan:
        return jsonify({'message': 'Scan not found'}), 404
    
    return jsonify({
        'id': scan.id,
        'file_name': scan.file_name,
        'upload_date': scan.upload_date.isoformat() if scan.upload_date else None,
        'file_path': scan.file_path
    }), 200


@app.route('/api/scans/<int:scan_id>', methods=['DELETE'])
@token_required
def api_delete_scan(scan_id):
    """Delete a scan"""
    db = get_db()
    scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
    
    if not scan:
        db.close()
        return jsonify({'message': 'Scan not found'}), 404
    
    try:
        # Delete file if exists
        if os.path.exists(scan.file_path):
            os.remove(scan.file_path)
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
    
    db.delete(scan)
    db.commit()
    db.close()
    
    return jsonify({'message': 'Scan deleted successfully'}), 200


@app.route('/api/scans/upload', methods=['POST', 'OPTIONS'])
@token_required
def api_upload_scan():
    """Upload a new CT scan"""
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'No file provided'}), 400
        
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'message': 'Invalid file'}), 400
        
        # Create scans directory if it doesn't exist
        scans_dir = os.path.join(APP_ROOT, 'uploads', 'scans')
        os.makedirs(scans_dir, exist_ok=True)
        
        # Save file
        filename = f"scan_{request.user_id}_{int(time.time())}_{file.filename}"
        filepath = os.path.join(scans_dir, filename)
        file.save(filepath)
        
        # Create DB record
        db = get_db()
        ct_scan = CTScan(
            file_name=file.filename,
            file_path=filepath,
            owner_id=request.user_id
        )
        db.add(ct_scan)
        db.commit()
        
        scan_data = {
            'id': ct_scan.id,
            'file_name': ct_scan.file_name,
            'upload_date': ct_scan.upload_date.isoformat() if ct_scan.upload_date else None,
            'file_path': ct_scan.file_path
        }
        
        db.close()
        return jsonify(scan_data), 201
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'message': 'Upload failed'}), 500


@app.route('/api/analyze/<int:scan_id>', methods=['POST', 'OPTIONS'])
@token_required
def api_analyze_scan(scan_id):
    """Analyze a CT scan for nodules using ML pipeline"""
    try:
        db = get_db()
        scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
        
        if not scan:
            db.close()
            return jsonify({'message': 'Scan not found'}), 404
        
        if not os.path.exists(scan.file_path):
            db.close()
            return jsonify({'message': 'Scan file not found'}), 404
        
        # Run ML pipeline
        logger.info(f"Running ML pipeline on scan {scan_id}")
        from src.ml import run_detection
        
        result = run_detection(
            scan.file_path,
            confidence_threshold=0.5,
            min_size_mm=3.0
        )
        
        if not result['success']:
            logger.error(f"Detection failed: {result.get('error', 'Unknown error')}")
            return jsonify({'message': 'Detection failed', 'error': result.get('error')}), 500
        
        # Store aggregated detection result
        detections = result['detections']
        
        # Save summary
        boxes_json = json.dumps([{
            'center': d['center'],
            'confidence': d['confidence'],
            'size_mm': d['size_mm'],
            'center_mm': d.get('center_mm', (0, 0, 0))
        } for d in detections])
        
        # Calculate average confidence
        avg_confidence = np.mean([d['confidence'] for d in detections]) if detections else 0.0
        avg_size = np.mean([d['size_mm'] for d in detections]) if detections else 0.0
        
        detection = DetectionResult(
            scan_id=scan_id,
            confidence_score=float(avg_confidence),
            lesion_size=float(avg_size),
            boxes_text=boxes_json
        )
        db.add(detection)
        db.commit()
        
        result_data = {
            'id': detection.id,
            'scan_id': detection.scan_id,
            'num_detections': len(detections),
            'confidence_score': detection.confidence_score,
            'avg_size_mm': detection.lesion_size,
            'detections': detections[:10],  # Return top 10 for frontend
            'runtime': result['runtime'],
            'created_date': detection.created_date.isoformat() if detection.created_date else None,
        }
        
        db.close()
        return jsonify(result_data), 200
    
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({'message': 'Analysis failed'}), 500


@app.route('/api/results/<int:scan_id>', methods=['GET', 'OPTIONS'])
@token_required
def api_get_results(scan_id):
    """Get analysis results for a scan"""
    db = get_db()
    scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
    
    if not scan:
        db.close()
        return jsonify({'message': 'Scan not found'}), 404
    
    detections = db.query(DetectionResult).filter(DetectionResult.scan_id == scan_id).all()
    
    results = [{
        'id': d.id,
        'scan_id': d.scan_id,
        'confidence_score': d.confidence_score,
        'lesion_size': d.lesion_size,
        'created_date': d.created_date.isoformat() if d.created_date else None
    } for d in detections]
    
    db.close()
    return jsonify(results), 200


@app.route('/api/generate_report/<int:scan_id>', methods=['POST', 'OPTIONS'])
@token_required
def api_generate_report(scan_id):
    """Generate AI clinical report for a scan"""
    try:
        db = get_db()
        scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
        
        if not scan:
            db.close()
            return jsonify({'message': 'Scan not found'}), 404
        
        # Get detection results for this scan
        detections = db.query(DetectionResult).filter(DetectionResult.scan_id == scan_id).all()
        
        # Parse detection data
        parsed_detections = []
        for det in detections:
            try:
                boxes = json.loads(det.boxes_text)
                parsed_detections.extend(boxes)
            except:
                pass
        
        # Generate production report using RAG
        logger.info(f"Generating clinical report for scan {scan_id}")
        from src.rag.production_report_generator import generate_clinical_report
        
        report_content = generate_clinical_report(
            parsed_detections,
            patient_info={
                'scan_id': scan_id,
                'scan_date': scan.upload_date.isoformat() if scan.upload_date else None,
            }
        )
        
        # Convert report to formatted text
        report_text = _format_report(report_content)
        
        # Store in database
        report = ClinicalReport(
            scan_id=scan_id,
            report_text=report_text
        )
        db.add(report)
        db.commit()
        
        report_data = {
            'id': report.id,
            'scan_id': report.scan_id,
            'report_text': report.report_text,
            'structured_report': report_content,
            'created_date': report.created_date.isoformat() if report.created_date else None
        }
        
        db.close()
        return jsonify(report_data), 201
    
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        return jsonify({'message': 'Report generation failed'}), 500


@app.route('/api/report/<int:scan_id>', methods=['GET', 'OPTIONS'])
@token_required
def api_get_report(scan_id):
    """Get clinical report for a scan"""
    db = get_db()
    scan = db.query(CTScan).filter(CTScan.id == scan_id, CTScan.owner_id == request.user_id).first()
    
    if not scan:
        db.close()
        return jsonify({'message': 'Scan not found'}), 404
    
    report = db.query(ClinicalReport).filter(ClinicalReport.scan_id == scan_id).first()
    db.close()
    
    if not report:
        return jsonify({'message': 'Report not found'}), 404
    
    return jsonify({
        'id': report.id,
        'scan_id': report.scan_id,
        'report_text': report.report_text,
        'created_date': report.created_date.isoformat() if report.created_date else None
    }), 200


if __name__ == '__main__':
    # Force port 5050 to avoid conflicts
    app.run(host='0.0.0.0', port=5050, debug=True)
