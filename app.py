from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
from functools import wraps
import re
from utils.image_helpers import save_image, delete_image, ALLOWED_EXTENSIONS, IMAGE_SIZES

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/restaurant_db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

mongo = PyMongo(app)

# Register a custom Jinja2 filter for datetime formatting
@app.template_filter('datetime')
def datetime_filter(value, format='%B %d, %Y %I:%M %p'):
    if value is None:
        return ''
    # If value is a string, try to parse it to datetime
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except Exception:
            return value
    return value.strftime(format)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Home page
@app.route('/')
def index():
    # Get featured menu items
    featured_items = list(mongo.db.menu_items.find({'featured': True}).limit(6))
    # Get restaurant info
    restaurant_info = mongo.db.restaurant_info.find_one()
    return render_template('index.html', featured_items=featured_items, restaurant_info=restaurant_info)

# Authentication routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        # Check if user already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'password': generate_password_hash(password),
            'user_type': 'customer',
            'created_at': datetime.utcnow()
        }
        
        result = mongo.db.users.insert_one(user_data)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = mongo.db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['user_type'] = user['user_type']
            
            if user['user_type'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# Menu routes
@app.route('/menu')
def menu():
    categories = list(mongo.db.menu_categories.find())
    menu_items = {}
    for category in categories:
        cat_id = str(category['_id'])
        items = list(mongo.db.menu_items.find({'category_id': cat_id}))
        # Ensure each item has an 'image' field for template compatibility
        for item in items:
            if 'images' in item and isinstance(item['images'], dict):
                # Prefer 'medium' size, fallback to any available
                item['image'] = item['images'].get('medium') or next(iter(item['images'].values()), None)
            elif 'image' not in item:
                item['image'] = None
        menu_items[cat_id] = items
    return render_template('menu.html', categories=categories, menu_items=menu_items)

# Reservation routes
@app.route('/reservations', methods=['GET', 'POST'])
@login_required
def reservations():
    if request.method == 'POST':
        # Validate reservation data
        date = request.form['date']
        time = request.form['time']
        guests = request.form['guests']
        
        if guests == 'more':
            flash('For groups larger than 10, please contact us directly.', 'error')
            return redirect(url_for('contact'))
            
        reservation_data = {
            'user_id': session['user_id'],
            'date': date,
            'time': time,
            'guests': int(guests),
            'seating': request.form.get('seating', 'no_preference'),
            'special_requests': request.form.get('special_requests', ''),
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        
        # Check if table is available
        existing_reservations = mongo.db.reservations.find({
            'date': date,
            'time': time,
            'status': {'$in': ['pending', 'confirmed']}
        })
        
        total_guests = sum(r.get('guests', 0) for r in existing_reservations)
        if total_guests + int(guests) > 50:  # Assuming restaurant capacity is 50
            flash('Sorry, we are fully booked for this time. Please select another time or contact us.', 'error')
            return redirect(url_for('reservations'))
        
        mongo.db.reservations.insert_one(reservation_data)
        flash('Reservation request submitted successfully! We will confirm your reservation shortly.', 'success')
        return redirect(url_for('my_reservations'))
    
    # Get user information for the form
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    if user:
        session['user_email'] = user.get('email')
        session['user_phone'] = user.get('phone')
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('reservations.html', today=today)

@app.route('/my-reservations')
@login_required
def my_reservations():
    reservations = list(mongo.db.reservations.find({'user_id': session['user_id']}).sort('created_at', -1))
    # Convert reservation['date'] from string to datetime.date for safe comparison in Jinja
    for reservation in reservations:
        if 'date' in reservation and isinstance(reservation['date'], str):
            try:
                reservation['date'] = datetime.strptime(reservation['date'], '%Y-%m-%d').date()
            except Exception:
                pass  # Leave as is if parsing fails
    today = datetime.utcnow().date()
    return render_template('my_reservations.html', reservations=reservations, today=today)

@app.route('/cancel-reservation/<reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    # Only allow the user who owns the reservation to cancel it
    reservation = mongo.db.reservations.find_one({'_id': ObjectId(reservation_id), 'user_id': session['user_id']})
    if reservation:
        mongo.db.reservations.update_one({'_id': ObjectId(reservation_id)}, {'$set': {'status': 'cancelled'}})
        flash('Reservation cancelled successfully.', 'success')
    else:
        flash('Reservation not found or not authorized.', 'error')
    return redirect(url_for('my_reservations'))

# Online ordering routes
@app.route('/order')
@login_required
def order():
    categories = list(mongo.db.menu_categories.find())
    menu_items = {}
    for category in categories:
        cat_id = str(category['_id'])
        items = list(mongo.db.menu_items.find({'category_id': cat_id}))
        # Ensure each item has an 'image' field for template compatibility
        for item in items:
            if 'images' in item and isinstance(item['images'], dict):
                item['image'] = item['images'].get('medium') or next(iter(item['images'].values()), None)
            elif 'image' not in item:
                item['image'] = None
        menu_items[cat_id] = items
    return render_template('order.html', categories=categories, menu_items=menu_items)

@app.route('/cart')
@login_required
def cart():
    # Get user information for delivery details
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    return render_template('cart.html', user=user)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_items = request.json.get('items', [])
    total_amount = request.json.get('total', 0)
    delivery_address = request.json.get('address', '')
    phone = request.json.get('phone', '')
    notes = request.json.get('notes', '')
    
    order_data = {
        'user_id': session['user_id'],
        'items': cart_items,
        'total_amount': total_amount,
        'delivery_address': delivery_address,
        'phone': phone,
        'notes': notes,
        'status': 'pending',
        'order_date': datetime.utcnow(),
        'estimated_delivery': datetime.utcnow() + timedelta(minutes=45)
    }
    
    result = mongo.db.orders.insert_one(order_data)
    
    # Add notification for restaurant staff
    notification_data = {
        'type': 'new_order',
        'order_id': str(result.inserted_id),
        'user_id': session['user_id'],
        'message': f'New order received from {session["user_name"]}',
        'created_at': datetime.utcnow(),
        'read': False
    }
    mongo.db.notifications.insert_one(notification_data)
    
    return jsonify({'success': True, 'order_id': str(result.inserted_id)})

@app.route('/order-confirmation')
@login_required
def order_confirmation():
    order_id = request.args.get('order_id')
    if not order_id:
        return redirect(url_for('my_orders'))
    
    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    if not order or str(order['user_id']) != session['user_id']:
        flash('Order not found', 'error')
        return redirect(url_for('my_orders'))
        
    return render_template('order_confirmation.html', order=order)

@app.route('/my-orders')
@login_required
def my_orders():
    orders = list(mongo.db.orders.find({
        'user_id': session['user_id']
    }).sort('order_date', -1))
    
    return render_template('my_orders.html', orders=orders)

# Gallery and About pages
@app.route('/gallery')
def gallery():
    gallery_images = list(mongo.db.gallery.find())
    # Ensure each image dict has a 'filename' key for template compatibility
    for img in gallery_images:
        if 'filename' not in img:
            # Try to use medium size as default filename
            if 'images' in img and isinstance(img['images'], dict):
                img['filename'] = img['images'].get('medium') or next(iter(img['images'].values()), None)
            else:
                img['filename'] = None
    return render_template('gallery.html', images=gallery_images)

@app.route('/about')
def about():
    restaurant_info = mongo.db.restaurant_info.find_one()
    return render_template('about.html', restaurant_info=restaurant_info)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        contact_data = {
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form.get('phone', ''),
            'subject': request.form['subject'],
            'message': request.form['message'],
            'created_at': datetime.utcnow(),
            'status': 'unread'
        }
        
        mongo.db.contact_messages.insert_one(contact_data)
        flash('Thank you for your message. We will get back to you soon!', 'success')
        return redirect(url_for('contact'))
        
    restaurant_info = mongo.db.restaurant_info.find_one()
    return render_template('contact.html', restaurant_info=restaurant_info)

# Admin routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get dashboard statistics
    total_orders = mongo.db.orders.count_documents({})
    pending_reservations = mongo.db.reservations.count_documents({'status': 'pending'})
    total_customers = mongo.db.users.count_documents({'user_type': 'customer'})
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = mongo.db.orders.count_documents({
        'order_date': {'$gte': today_start}
    })
    
    stats = {
        'total_orders': total_orders,
        'pending_reservations': pending_reservations,
        'total_customers': total_customers,
        'today_orders': today_orders
    }
    
    # Get recent orders
    recent_orders = list(mongo.db.orders.find()
        .sort('order_date', -1)
        .limit(5))
    
    # Get recent reservations
    recent_reservations = list(mongo.db.reservations.find()
        .sort('created_at', -1)
        .limit(5))
    
    # Add user names to reservations
    for reservation in recent_reservations:
        user = mongo.db.users.find_one({'_id': ObjectId(reservation['user_id'])})
        reservation['user_name'] = user['name'] if user else 'Unknown'
    
    today_date = datetime.utcnow().strftime('%B %d, %Y')
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_orders=recent_orders,
                         recent_reservations=recent_reservations,
                         today_date=today_date)

@app.route('/admin/menu')
@admin_required
def admin_menu():
    categories = list(mongo.db.menu_categories.find())
    menu_items = list(mongo.db.menu_items.find())
    return render_template('admin/menu.html', categories=categories, menu_items=menu_items)

@app.route('/admin/menu/add-category', methods=['POST'])
@admin_required
def add_category():
    category_data = {
        'name': request.form['name'],
        'description': request.form.get('description', ''),
        'created_at': datetime.utcnow()
    }
    mongo.db.menu_categories.insert_one(category_data)
    flash('Category added successfully', 'success')
    return redirect(url_for('admin_menu'))

@app.route('/admin/menu/add-item', methods=['POST'])
@admin_required
def add_menu_item():
    try:
        # Handle image upload
        image_data = None
        if 'image' in request.files:
            image = request.files['image']
            if image.filename:
                image_data = save_image(
                    image, 
                    folder='uploads/menu',
                    sizes={
                        'thumbnail': (150, 150),
                        'medium': (400, 300)
                    }
                )
        
        item_data = {
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'category_id': request.form['category_id'],
            'featured': 'featured' in request.form,
            'available': True,
            'created_at': datetime.utcnow(),
            'images': image_data
        }
        
        result = mongo.db.menu_items.insert_one(item_data)
        flash('Menu item added successfully', 'success')
    except Exception as e:
        flash(f'Error adding menu item: {str(e)}', 'error')
    
    return redirect(url_for('admin_menu'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = list(mongo.db.orders.find().sort('order_date', -1))
    # Get user details for each order
    for order in orders:
        user = mongo.db.users.find_one({'_id': ObjectId(order['user_id'])})
        order['user_name'] = user['name'] if user else 'Unknown'
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    reservations = list(mongo.db.reservations.find().sort('created_at', -1))
    # Get user details for each reservation
    for reservation in reservations:
        user = mongo.db.users.find_one({'_id': ObjectId(reservation['user_id'])})
        reservation['user_name'] = user['name'] if user else 'Unknown'
        reservation['user_phone'] = user['phone'] if user else 'Unknown'
    return render_template('admin/reservations.html', reservations=reservations)

@app.route('/admin/reservation/update/<reservation_id>', methods=['POST'])
@admin_required
def update_reservation_status():
    reservation_id = request.form['reservation_id']
    status = request.form['status']
    
    mongo.db.reservations.update_one(
        {'_id': ObjectId(reservation_id)},
        {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
    )
    
    flash('Reservation status updated', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/restaurant-info', methods=['GET', 'POST'])
@admin_required
def admin_restaurant_info():
    if request.method == 'POST':
        info_data = {
            'name': request.form['name'],
            'story': request.form['story'],
            'address': request.form['address'],
            'phone': request.form['phone'],
            'email': request.form['email'],
            'hours': request.form['hours'],
            'updated_at': datetime.utcnow()
        }
        
        mongo.db.restaurant_info.update_one(
            {},
            {'$set': info_data},
            upsert=True
        )
        flash('Restaurant information updated', 'success')
    
    restaurant_info = mongo.db.restaurant_info.find_one()
    return render_template('admin/restaurant_info.html', restaurant_info=restaurant_info)

@app.route('/admin/gallery')
@admin_required
def admin_gallery():
    gallery_images = list(mongo.db.gallery.find().sort('created_at', -1))
    return render_template('admin/gallery.html', images=gallery_images)

@app.route('/admin/gallery/add', methods=['POST'])
@admin_required
def add_gallery_image():
    try:
        if 'image' not in request.files:
            flash('No image file provided', 'error')
            return redirect(url_for('admin_gallery'))
            
        image = request.files['image']
        if image.filename == '':
            flash('No image selected', 'error')
            return redirect(url_for('admin_gallery'))
            
        image_data = save_image(
            image,
            folder='uploads/gallery',
            sizes={
                'thumbnail': (300, 300),
                'medium': (800, 600),
                'large': (1200, 900)
            }
        )
        
        if not image_data:
            flash('Invalid image file', 'error')
            return redirect(url_for('admin_gallery'))
            
        gallery_data = {
            'title': request.form.get('title', ''),
            'caption': request.form.get('caption', ''),
            'category': request.form.get('category', 'general'),
            'images': image_data,
            'created_at': datetime.utcnow(),
            'active': True
        }
        
        mongo.db.gallery.insert_one(gallery_data)
        flash('Image added to gallery successfully', 'success')
        
    except Exception as e:
        flash(f'Error adding gallery image: {str(e)}', 'error')
        
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/delete/<image_id>')
@admin_required
def delete_gallery_image(image_id):
    try:
        image = mongo.db.gallery.find_one({'_id': ObjectId(image_id)})
        if image and 'images' in image:
            # Delete physical files
            for size_path in image['images'].values():
                filename = os.path.basename(size_path)
                delete_image(filename, folder='uploads/gallery')
            
            # Remove from database
            mongo.db.gallery.delete_one({'_id': ObjectId(image_id)})
            flash('Gallery image deleted successfully', 'success')
        else:
            flash('Image not found', 'error')
            
    except Exception as e:
        flash(f'Error deleting gallery image: {str(e)}', 'error')
        
    return redirect(url_for('admin_gallery'))

# Initialize admin user if not exists
def init_admin():
    admin = mongo.db.users.find_one({'user_type': 'admin'})
    if not admin:
        admin_data = {
            'name': 'Restaurant Admin',
            'email': 'admin@restaurant.com',
            'phone': '1234567890',
            'password': generate_password_hash('admin123'),
            'user_type': 'admin',
            'created_at': datetime.utcnow()
        }
        mongo.db.users.insert_one(admin_data)
        print("Admin user created - Email: admin@restaurant.com, Password: admin123")

if __name__ == '__main__':
    init_admin()
    app.run(debug=True)
