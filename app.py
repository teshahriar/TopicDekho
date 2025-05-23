from flask import Flask, render_template, request, redirect, session, flash, url_for
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Setup MongoDB client and DB
client = MongoClient(os.getenv("MONGO_URI"))
db = client["topicdekho"]
videos = db["videos"]
request_collection = db['request']  

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Helper to convert "mm:ss" string to total seconds (int)
def time_to_seconds(time_str):
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 3:  # Optional support for hh:mm:ss
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return 0

@app.route('/')
def home():
    all_videos = list(videos.find().sort("added_on", -1))
    return render_template("home.html", videos=all_videos)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results_cursor = videos.find({"title": {"$regex": query, "$options": "i"}})
    results = list(results_cursor)
    return render_template("search.html", videos=results, query=query)



@app.route('/watch/<video_id>')
def watch(video_id):
    video = videos.find_one({"_id": video_id})
    if not video:
        return "Video not found", 404
    return render_template("watch.html", video=video)

@app.route('/admin/login', methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route('/admin/logout')
def admin_logout():
    session.pop("admin", None)
    flash("Logged out successfully", "info")
    return redirect(url_for("admin_login"))

@app.route('/admin/dashboard', methods=["GET", "POST"])
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        yt_link = request.form.get("youtube", "").strip()
        start = request.form.get("start", "").strip()
        end = request.form.get("end", "").strip()

        # Basic validation
        if not title or not yt_link or not start or not end:
            flash("Please fill in all fields", "warning")
            return redirect(url_for("admin_dashboard"))

        # Extract YouTube video ID from link
        if "v=" in yt_link:
            youtube_id = yt_link.split("v=")[-1].split("&")[0]
        else:
            # Support shortened URLs like youtu.be
            if "youtu.be/" in yt_link:
                youtube_id = yt_link.split("youtu.be/")[-1].split("?")[0]
            else:
                flash("Invalid YouTube link format", "danger")
                return redirect(url_for("admin_dashboard"))

        # Convert start and end time to seconds
        start_sec = time_to_seconds(start)
        end_sec = time_to_seconds(end)

        if start_sec >= end_sec:
            flash("Start time must be less than end time", "danger")
            return redirect(url_for("admin_dashboard"))

        # Prepare video document
        video_doc = {
            "_id": youtube_id,
            "title": title,
            "youtube_id": youtube_id,
            "start": start,
            "end": end,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "added_on": datetime.utcnow()
        }

        try:
            # Insert or update video (upsert)
            videos.update_one({"_id": youtube_id}, {"$set": video_doc}, upsert=True)
            flash("Video added/updated successfully!", "success")
        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")

        return redirect(url_for("admin_dashboard"))

    # GET request: show all videos for admin
    all_videos = list(videos.find().sort("added_on", -1))
    return render_template("admin_panel.html", videos=all_videos)

@app.route('/request', methods=['GET', 'POST'])
def request_topic():
    if request.method == 'POST':
        name = request.form.get('name')
        telegram = request.form.get('telegram')
        topic = request.form.get('topic')
        
        if name and telegram and topic:
            request_collection.insert_one({
                'name': name,
                'telegram': telegram,
                'topic': topic
            })
            flash("Your request has been sent successfully!", "success")
            return redirect(url_for('request_topic'))
        else:
            flash("❌ Please fill in all fields.", "danger")

    return render_template('request.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(debug=True)
