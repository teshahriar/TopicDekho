from flask import Flask, render_template, request, redirect, session, flash, url_for
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import os
from bson import ObjectId

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Setup MongoDB client and DB
client = MongoClient(os.getenv("MONGO_URI"))
db = client["topicdekho"]
videos = db["videos"]
request_collection = db['request']  
playlists_collection = db['playlists']

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
        youtube_id = ""
        if "v=" in yt_link:
            youtube_id = yt_link.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in yt_link:
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

        # Generate unique ID for the video clip
        clip_id = f"{youtube_id}_{start_sec}_{end_sec}"

        # Prepare video document
        video_doc = {
            "_id": clip_id,
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
            videos.update_one({"_id": clip_id}, {"$set": video_doc}, upsert=True)
            flash("Video clip added/updated successfully!", "success")
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

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('404.html'), 500

@app.route('/listplay')
def list_playlists():
    playlists = list(playlists_collection.find())
    
    for playlist in playlists:
        video_infos = []
        for vid in playlist.get('video_ids', []):
            # vid is YouTube video ID string like 'K-OzRLh5700'
            video_doc = videos.find_one({"_id": vid})  # if _id in videos is also the YouTube ID string
            if video_doc:
                video_infos.append({
                    "id": vid,
                    "title": video_doc.get("title", "Untitled"),
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                })
        playlist["videos"] = video_infos
    
    return render_template('listplay.html', playlists=playlists)

syllabus = {
    "Bangla 1st Paper": ["Goddo", "Poddo", "Natok", "Uponnash"],
    "Bangla 2nd Paper": ["Bekoron", "Nirmiti"],
    "English 1st Paper": ["Reading Comprehension", "Writing"],
    "English 2nd Paper": ["Grammer", "Writing"],
    "ICT": ["Chapter 1", "Chapter 2", "Number system", "HTML", "C-programming"],
    "Physics 1st Paper": ["ভৌতজগৎ ও পরিমাপ", "ভেক্টর", "নিউটনিয়ান বলবিদ্যা", "কাজ ক্ষমতা ও শক্তি", "মহাকর্ষ ও অভিকর্ষ", "পদার্থের গাঠনিক ধর্ম", "পর্যাবৃত্তিক গতি", "আদর্শ গ্যাস ও গ্যাসের গতিতত্ত্ব"],
    "Physics 2nd Paper": ["তাপগতিবিদ্যা", "স্থির তড়িৎ", "চল তড়িৎ", "ভৌত আলোকবিজ্ঞান", "আধুনিক আলোকবিজ্ঞান সূচনা", "পরমাণু মডেল এবং নিউক্লিয়ার পদার্থবিজ্ঞান", "সেমিকন্ডাক্টর"],
    "Chemistry 1st Paper": ["গুণগত রসায়ন", "মৌলের পর্যায়বৃত্ত ধর্ম ও রাসায়নিক বন্ধন", "রাসায়নিক পরিবর্তন", "কর্মমুখী রসায়ন"],
    "Chemistry 2nd Paper": ["পরিবেশ রসায়ন", "জৈব রসায়ন", "পরিমাণগত রসায়ন", "তড়িৎ রসায়ন"],
    "Biology 1st Paper": ["কোষ ও এর গঠন", "কোষ বিভাজন", "অণুজীব", "নগ্নবীজী ও আবৃতবীজী", "টিস্যু ও টিস্যুতন্ত্র", "উদ্ভিদ শারীরতত্ত্ব", "জীবপ্রযুক্তি"],
    "Biology 2nd Paper": ["প্রাণীর বিভিন্নতা ও শ্রেণিবিন্যাস", "প্রাণীর পরিচিতি", "পরিপাক ও শোষন", "রক্ত ও সঞ্চালন", "শ্বসন ও শ্বাসক্রিয়া", "চলন ও অঙ্গচালনা", "জিনতত্ত্ব ও বিবর্তন"],
    "Higher Mathematics 1st Paper": ["ম্যাট্রিক্স ও নির্ণায়ক", "সরলরেখা", "বৃত্ত", "সংযুক্ত কোণের ত্রিকোণমিতিক অনুপাত", "অন্তরীকরণ", "যোগজীকরণ"],
    "Higher Mathematics 2nd Paper": ["জটিল সংখ্যা", "বহুপদী ও বহুপদী সমীকরণ", "কনিক", "বিপরীত ত্রিকোণমিতিক ফাংশন ও ত্রিকোণমিতিক সমীকরণ","স্থিতিবিদ্যা", "সমতলে বস্তুকণার গতি"]
}

@app.route('/create_playlist', methods=['GET', 'POST'])
def create_playlist():
    if request.method == 'POST':
        subject = request.form.get('subject')
        chapter = request.form.get('chapter')
        video_ids = request.form.getlist('video_ids')  
        if not subject or not chapter or not video_ids:
            flash("Please select subject, chapter and at least one video.")
            return redirect(url_for('create_playlist'))

        playlist_doc = {
            "subject": subject,
            "chapter": chapter,
            "video_ids": video_ids, 
            "hidden": True
        }

        playlists_collection.insert_one(playlist_doc)

        flash("Playlist created successfully!")
        return redirect(url_for('list_playlists'))

    videos_list = list(videos.find())
    return render_template('create_playlist.html', syllabus=syllabus, videos=videos_list)

if __name__ == "__main__":
    app.run(debug=True)
