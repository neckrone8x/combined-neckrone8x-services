from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from flask_sqlalchemy import SQLAlchemy

from datetime import datetime, timedelta

import os
import re

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    app.secret_key = "neckrone8x-development-secret-key"


# ============================================================
# TEMPLATE GLOBALS
# ============================================================

@app.context_processor
def inject_template_globals():
    return {"current_year": datetime.utcnow().year}


# ============================================================
# GET VISITOR IP ADDRESS
# ============================================================

def get_visitor_ip():

    cloudflare_ip = request.headers.get("CF-Connecting-IP")

    if cloudflare_ip:
        cloudflare_ip = cloudflare_ip.strip()
        if cloudflare_ip:
            return cloudflare_ip

    remote_ip = request.remote_addr

    if remote_ip:
        return remote_ip.strip()

    return "unknown"


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

database_url = os.getenv("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(BASE_DIR, "stories.db")
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# STORY MODEL
# ============================================================

class Story(db.Model):

    __tablename__ = "stories"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False, default="General")
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), nullable=False, default="Anonymous")
    cover_image = db.Column(db.String(500), nullable=True)
    published = db.Column(db.Boolean, default=False)
    read_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reads = db.relationship("StoryRead", backref="story", cascade="all, delete-orphan")
    reactions = db.relationship("Reaction", backref="story", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="story", cascade="all, delete-orphan")


# ============================================================
# STORY READ MODEL
# ============================================================

class StoryRead(db.Model):

    __tablename__ = "story_reads"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(
        db.Integer,
        db.ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False
    )
    ip_address = db.Column(db.String(45), nullable=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ============================================================
# REACTION MODEL
# ============================================================

class Reaction(db.Model):

    __tablename__ = "reactions"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(
        db.Integer,
        db.ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False
    )
    reaction_type = db.Column(db.String(20), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ============================================================
# COMMENT MODEL
# ============================================================

class Comment(db.Model):

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(
        db.Integer,
        db.ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False
    )
    name = db.Column(db.String(80), nullable=False, default="Anonymous")
    content = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return redirect(url_for("stories"))


# ============================================================
# PUBLIC STORIES
# ============================================================

@app.route("/stories")
def stories():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    page = request.args.get("page", 1, type=int)

    if page < 1:
        page = 1

    query = Story.query.filter_by(published=True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Story.title.ilike(search_pattern),
                Story.author.ilike(search_pattern),
                Story.category.ilike(search_pattern),
                Story.content.ilike(search_pattern)
            )
        )

    if category:
        query = query.filter(Story.category.ilike(category))

    pagination = query.order_by(Story.created_at.desc()).paginate(
        page=page, per_page=6, error_out=False
    )

    stories = pagination.items

    categories = [
        "General", "Confession", "Experience", "News",
        "Relationship", "Marriage", "Life", "Novels", "18+", "Other"
    ]

    return render_template(
        "stories/index.html",
        stories=stories,
        search=search,
        category=category,
        categories=categories,
        pagination=pagination
    )


# ============================================================
# VIEW SINGLE STORY
# ============================================================

@app.route("/stories/<slug>")
def view_story(slug):

    story = Story.query.filter_by(slug=slug, published=True).first_or_404()

    # 18+ AGE GATE
    if story.category == "18+":
        verified_stories = session.get("age_verified_stories", [])
        if not isinstance(verified_stories, list):
            verified_stories = []
        if story.id not in verified_stories:
            return render_template("stories/age_gate.html", story=story)

    # RECORD ONE READ PER VISITOR PER STORY
    visitor_ip = get_visitor_ip()

    existing_read = StoryRead.query.filter_by(
        story_id=story.id,
        ip_address=visitor_ip
    ).first()

    if not existing_read:
        story.read_count = (story.read_count or 0) + 1
        db.session.add(StoryRead(story_id=story.id, ip_address=visitor_ip))
        db.session.commit()

    # REACTIONS
    reaction_types = ["love", "like", "laugh", "wow", "sad"]
    reaction_counts = {}

    for rtype in reaction_types:
        reaction_counts[rtype] = Reaction.query.filter_by(
            story_id=story.id,
            reaction_type=rtype
        ).count()

    user_reaction = Reaction.query.filter_by(
        story_id=story.id,
        ip_address=visitor_ip
    ).first()

    user_reaction_type = user_reaction.reaction_type if user_reaction else None

    # COMMENTS
    comments = Comment.query.filter_by(
        story_id=story.id,
        approved=True
    ).order_by(Comment.created_at.desc()).all()

    return render_template(
        "stories/story.html",
        story=story,
        reaction_counts=reaction_counts,
        user_reaction_type=user_reaction_type,
        comments=comments
    )


# ============================================================
# 18+ AGE VERIFICATION
# ============================================================

@app.route("/stories/<slug>/verify-age")
def verify_age(slug):

    story = Story.query.filter_by(slug=slug, published=True).first_or_404()

    if story.category != "18+":
        return redirect(url_for("view_story", slug=story.slug))

    verified_stories = session.get("age_verified_stories", [])
    if not isinstance(verified_stories, list):
        verified_stories = []

    if story.id not in verified_stories:
        verified_stories.append(story.id)

    session["age_verified_stories"] = verified_stories
    session.modified = True

    return redirect(url_for("view_story", slug=story.slug))


# ============================================================
# REACT TO STORY
# ============================================================

@app.route("/stories/<slug>/react/<reaction_type>", methods=["POST"])
def react_to_story(slug, reaction_type):

    story = Story.query.filter_by(slug=slug, published=True).first_or_404()

    if reaction_type not in {"love", "like", "laugh", "wow", "sad"}:
        return redirect(url_for("view_story", slug=slug))

    visitor_ip = get_visitor_ip()

    existing = Reaction.query.filter_by(
        story_id=story.id,
        ip_address=visitor_ip
    ).first()

    if existing:
        if existing.reaction_type == reaction_type:
            # Same reaction — remove it
            db.session.delete(existing)
        else:
            # Different reaction — swap it
            existing.reaction_type = reaction_type
    else:
        db.session.add(Reaction(
            story_id=story.id,
            reaction_type=reaction_type,
            ip_address=visitor_ip
        ))

    db.session.commit()

    return redirect(url_for("view_story", slug=slug) + "#reactions")


# ============================================================
# ADD COMMENT
# ============================================================

@app.route("/stories/<slug>/comment", methods=["POST"])
def add_comment(slug):

    story = Story.query.filter_by(slug=slug, published=True).first_or_404()

    name = (request.form.get("name", "") or "").strip()
    content = (request.form.get("content", "") or "").strip()

    if not content:
        return redirect(url_for("view_story", slug=slug) + "#comments")

    if not name:
        name = "Anonymous"

    db.session.add(Comment(
        story_id=story.id,
        name=name[:80],
        content=content,
        ip_address=get_visitor_ip()
    ))
    db.session.commit()

    return redirect(url_for("view_story", slug=slug) + "#comments")


# ============================================================
# PUBLIC STORY SUBMISSION
# ============================================================

@app.route("/stories/submit", methods=["GET", "POST"])
def submit_story():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "General").strip()
        content = request.form.get("content", "").strip()
        author = request.form.get("author", "Anonymous").strip()

        if not title or not content:
            return render_template(
                "stories/submit.html",
                error="Title and story content are required."
            )

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "story"

        original_slug = slug
        counter = 2
        while Story.query.filter_by(slug=slug).first():
            slug = original_slug + "-" + str(counter)
            counter += 1

        story = Story(
            title=title,
            slug=slug,
            category=(category or "General"),
            content=content,
            author=(author or "Anonymous"),
            published=False,
            read_count=0
        )

        db.session.add(story)
        db.session.commit()

        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Story Submitted — Neckrone8x</title>
            <style>
                * { box-sizing: border-box; }
                body {
                    margin: 0; min-height: 100vh;
                    display: flex; justify-content: center; align-items: center;
                    background: #080c14; color: white;
                    font-family: Arial, sans-serif;
                    text-align: center; padding: 20px;
                }
                .box {
                    max-width: 550px; padding: 40px;
                    background: #0d1320;
                    border: 1px solid #202938;
                    border-radius: 12px;
                }
                h1 { margin-top: 0; }
                p { color: #aab2c0; line-height: 1.6; }
                a {
                    display: inline-block; margin-top: 20px;
                    color: #00d9ff; text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Story Submitted</h1>
                <p>Thank you for sharing your story.</p>
                <p>Your submission has been received and will be reviewed before publication.</p>
                <a href="/stories">&#8592; Back to Stories</a>
            </div>
        </body>
        </html>
        """

    return render_template("stories/submit.html", error=None)


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if not admin_username or not admin_password:
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError(
                    "ADMIN_USERNAME and ADMIN_PASSWORD must be set in production"
                )
            admin_username = admin_username or "admin"
            admin_password = admin_password or "admin123"

        if username == admin_username and password == admin_password:
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))

        return render_template(
            "admin/login.html",
            error="Invalid username or password."
        )

    return render_template("admin/login.html")


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def dashboard():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    published_count = Story.query.filter_by(published=True).count()
    pending_count = Story.query.filter_by(published=False).count()

    total_reads = db.session.query(
        db.func.sum(Story.read_count)
    ).filter(Story.published == True).scalar() or 0

    now = datetime.utcnow()

    stories_this_month = Story.query.filter(
        Story.published == True,
        db.extract("month", Story.created_at) == now.month,
        db.extract("year", Story.created_at) == now.year
    ).count()

    recent_stories = Story.query.order_by(
        Story.created_at.desc()
    ).limit(5).all()

    top_stories = Story.query.filter_by(published=True).order_by(
        Story.read_count.desc()
    ).limit(5).all()

    pending_stories = Story.query.filter_by(published=False).order_by(
        Story.created_at.desc()
    ).all()

    return render_template(
        "admin/dashboard.html",
        published_count=published_count,
        pending_count=pending_count,
        total_reads=total_reads,
        stories_this_month=stories_this_month,
        recent_stories=recent_stories,
        pending_stories=pending_stories,
        top_stories=top_stories,
        pending_submissions=pending_count
    )


# ============================================================
# CREATE STORY
# ============================================================

@app.route("/admin/create-story", methods=["GET", "POST"])
def create_story():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "General").strip()
        content = request.form.get("content", "").strip()
        author = request.form.get("author", "Anonymous").strip()
        published = (request.form.get("published") == "on")

        if not title or not content:
            return render_template(
                "admin/create_story.html",
                error="Title and story content are required."
            )

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "story"

        original_slug = slug
        counter = 2
        while Story.query.filter_by(slug=slug).first():
            slug = original_slug + "-" + str(counter)
            counter += 1

        story = Story(
            title=title,
            slug=slug,
            category=(category or "General"),
            content=content,
            author=(author or "Anonymous"),
            published=published,
            read_count=0
        )

        db.session.add(story)
        db.session.commit()

        return redirect(url_for("manage_stories"))

    return render_template("admin/create_story.html")


# ============================================================
# MANAGE PUBLISHED STORIES
# ============================================================

@app.route("/admin/stories")
def manage_stories():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    stories = Story.query.filter_by(published=True).order_by(
        Story.created_at.desc()
    ).all()

    return render_template("admin/stories.html", stories=stories)


# ============================================================
# MANAGE SUBMISSIONS
# ============================================================

@app.route("/admin/submissions")
def manage_submissions():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    submissions = Story.query.filter_by(published=False).order_by(
        Story.created_at.desc()
    ).all()

    return render_template("admin/submissions.html", submissions=submissions)


# ============================================================
# REVIEW STORY
# ============================================================

@app.route("/admin/stories/review/<int:story_id>")
def review_story(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)

    return render_template("admin/review_story.html", story=story)


# ============================================================
# APPROVE STORY
# ============================================================

@app.route("/admin/stories/approve/<int:story_id>", methods=["POST"])
def approve_story(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)
    story.published = True
    db.session.commit()

    return redirect(url_for("dashboard"))


# ============================================================
# EDIT STORY
# ============================================================

@app.route("/admin/stories/edit/<int:story_id>", methods=["GET", "POST"])
def edit_story(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "General").strip()
        content = request.form.get("content", "").strip()
        author = request.form.get("author", "Anonymous").strip()

        if not title or not content:
            return render_template(
                "admin/edit_story.html",
                story=story,
                error="Title and story content are required."
            )

        story.title = title
        story.category = (category or "General")
        story.content = content
        story.author = (author or "Anonymous")

        db.session.commit()

        return redirect(url_for("manage_stories"))

    return render_template("admin/edit_story.html", story=story)


# ============================================================
# STORY ANALYTICS
# ============================================================

@app.route("/admin/stories/analytics/<int:story_id>")
def story_analytics(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = datetime(now.year, now.month, 1)

    total_reads = StoryRead.query.filter_by(story_id=story.id).count()

    today_reads = StoryRead.query.filter(
        StoryRead.story_id == story.id,
        StoryRead.read_at >= today_start
    ).count()

    week_reads = StoryRead.query.filter(
        StoryRead.story_id == story.id,
        StoryRead.read_at >= week_start
    ).count()

    month_reads = StoryRead.query.filter(
        StoryRead.story_id == story.id,
        StoryRead.read_at >= month_start
    ).count()

    if story.read_count != total_reads:
        story.read_count = total_reads
        db.session.commit()

    unique_readers = db.session.query(
        db.func.count(db.func.distinct(StoryRead.ip_address))
    ).filter(
        StoryRead.story_id == story.id,
        StoryRead.ip_address.isnot(None)
    ).scalar() or 0

    reads_per_reader = (
        round(total_reads / unique_readers, 1) if unique_readers else 0
    )

    seven_days_ago = today_start - timedelta(days=6)

    day_rows = db.session.query(
        db.func.date(StoryRead.read_at).label("read_day"),
        db.func.count(StoryRead.id).label("read_total")
    ).filter(
        StoryRead.story_id == story.id,
        StoryRead.read_at.isnot(None),
        StoryRead.read_at >= seven_days_ago,
        StoryRead.read_at < (today_start + timedelta(days=1))
    ).group_by(
        db.func.date(StoryRead.read_at)
    ).order_by(
        db.func.date(StoryRead.read_at).asc()
    ).all()

    read_lookup = {str(row.read_day): row.read_total for row in day_rows}

    daily_reads = []
    for i in range(7):
        current_day = seven_days_ago + timedelta(days=i)
        current_day_string = current_day.strftime("%Y-%m-%d")
        daily_reads.append({
            "date": current_day_string,
            "reads": read_lookup.get(current_day_string, 0)
        })

    if day_rows:
        best_row = max(day_rows, key=lambda row: row.read_total)
        best_day_date = str(best_row.read_day)
        best_day_reads = best_row.read_total
        try:
            best_day_label = datetime.strptime(
                best_day_date, "%Y-%m-%d"
            ).strftime("%B %d, %Y")
        except ValueError:
            best_day_label = best_day_date
        best_day = {"date": best_day_label, "reads": best_day_reads}
    else:
        best_day = {"date": "No reads yet", "reads": 0}
        best_day_reads = 0
        best_day_label = "No reads yet"

    if daily_reads:
        max_daily_reads = max(item["reads"] for item in daily_reads)
        total_daily_reads = sum(item["reads"] for item in daily_reads)
        average_daily_reads = round(total_daily_reads / len(daily_reads), 1)
    else:
        max_daily_reads = 0
        average_daily_reads = 0

    recent_reads = StoryRead.query.filter_by(
        story_id=story.id
    ).order_by(
        StoryRead.read_at.desc()
    ).limit(10).all()

    for read in recent_reads:
        if not read.read_at:
            read.relative_time = "Unknown"
            continue
        seconds = (now - read.read_at).total_seconds()
        if seconds < 0:
            seconds = 0
        if seconds < 60:
            read.relative_time = "Just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            read.relative_time = (
                f"{minutes} minute" + ("s" if minutes != 1 else "") + " ago"
            )
        elif seconds < 86400:
            hours = int(seconds // 3600)
            read.relative_time = (
                f"{hours} hour" + ("s" if hours != 1 else "") + " ago"
            )
        elif seconds < 172800:
            read.relative_time = "Yesterday"
        else:
            read.relative_time = read.read_at.strftime("%B %d, %Y")

    return render_template(
        "admin/analytics.html",
        story=story,
        total_reads=total_reads,
        today_reads=today_reads,
        week_reads=week_reads,
        month_reads=month_reads,
        unique_readers=unique_readers,
        reads_per_reader=reads_per_reader,
        best_day=best_day,
        best_day_reads=best_day_reads,
        best_day_label=best_day_label,
        daily_reads=daily_reads,
        max_daily_reads=max_daily_reads,
        average_daily_reads=average_daily_reads,
        recent_reads=recent_reads
    )


# ============================================================
# OVERALL ANALYTICS
# ============================================================

@app.route("/admin/analytics")
def admin_analytics():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    total_reads = db.session.query(
        db.func.sum(Story.read_count)
    ).filter(Story.published == True).scalar() or 0

    published_stories = Story.query.filter_by(published=True).count()

    unique_readers = db.session.query(
        db.func.count(db.func.distinct(StoryRead.ip_address))
    ).join(
        Story, StoryRead.story_id == Story.id
    ).filter(
        Story.published == True,
        StoryRead.ip_address.isnot(None)
    ).scalar() or 0

    reads_per_reader = (
        round(total_reads / unique_readers, 1) if unique_readers else 0
    )

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = datetime(now.year, now.month, 1)

    today_reads = db.session.query(StoryRead.id).join(
        Story, StoryRead.story_id == Story.id
    ).filter(
        Story.published == True,
        StoryRead.read_at >= today_start
    ).count()

    week_reads = db.session.query(StoryRead.id).join(
        Story, StoryRead.story_id == Story.id
    ).filter(
        Story.published == True,
        StoryRead.read_at >= week_start
    ).count()

    month_reads = db.session.query(StoryRead.id).join(
        Story, StoryRead.story_id == Story.id
    ).filter(
        Story.published == True,
        StoryRead.read_at >= month_start
    ).count()

    top_stories = Story.query.filter_by(published=True).order_by(
        Story.read_count.desc()
    ).limit(5).all()

    daily_rows = db.session.query(
        db.func.date(StoryRead.read_at).label("read_day"),
        db.func.count(StoryRead.id).label("read_total")
    ).join(
        Story, StoryRead.story_id == Story.id
    ).filter(
        Story.published == True,
        StoryRead.read_at.isnot(None)
    ).group_by(
        db.func.date(StoryRead.read_at)
    ).order_by(
        db.func.date(StoryRead.read_at).asc()
    ).all()

    daily_reads = [
        {"date": str(row.read_day), "reads": row.read_total}
        for row in daily_rows
    ]

    return render_template(
        "admin/admin_analytics.html",
        total_reads=total_reads,
        total_stories=published_stories,
        unique_readers=unique_readers,
        reads_per_reader=reads_per_reader,
        today_reads=today_reads,
        week_reads=week_reads,
        month_reads=month_reads,
        top_stories=top_stories,
        daily_reads=daily_reads
    )


# ============================================================
# STORY READS
# ============================================================

@app.route("/admin/stories/reads/<int:story_id>")
def story_reads(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    pagination = StoryRead.query.filter_by(story_id=story.id).order_by(
        StoryRead.read_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    reads = pagination.items

    total_reads = StoryRead.query.filter_by(story_id=story.id).count()

    unique_readers = db.session.query(
        db.func.count(db.func.distinct(StoryRead.ip_address))
    ).filter(
        StoryRead.story_id == story.id,
        StoryRead.ip_address.isnot(None)
    ).scalar() or 0

    now = datetime.utcnow()
    today = now.date()

    for read in reads:
        if not read.read_at:
            read.read_at = now
        read_date = read.read_at.date()
        if read_date == today:
            read.date_group = "Today"
        elif read_date == (today - timedelta(days=1)):
            read.date_group = "Yesterday"
        else:
            read.date_group = read.read_at.strftime("%B %d, %Y")

        seconds = (now - read.read_at).total_seconds()
        if seconds < 0:
            seconds = 0
        if seconds < 60:
            read.relative_time = "Just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            read.relative_time = (
                f"{minutes} minute" + ("s" if minutes != 1 else "") + " ago"
            )
        elif seconds < 86400:
            hours = int(seconds // 3600)
            read.relative_time = (
                f"{hours} hour" + ("s" if hours != 1 else "") + " ago"
            )
        elif seconds < 172800:
            read.relative_time = "Yesterday"
        else:
            read.relative_time = read.read_at.strftime("%B %d, %Y")

    return render_template(
        "admin/story_reads.html",
        story=story,
        reads=reads,
        pagination=pagination,
        total_reads=total_reads,
        unique_readers=unique_readers
    )


# ============================================================
# DELETE STORY
# ============================================================

@app.route("/admin/stories/delete/<int:story_id>", methods=["POST"])
def delete_story(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)
    db.session.delete(story)
    db.session.commit()

    return redirect(url_for("manage_stories"))


# ============================================================
# PUBLISH / UNPUBLISH STORY
# ============================================================

@app.route("/admin/stories/toggle/<int:story_id>", methods=["POST"])
def toggle_story(story_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    story = Story.query.get_or_404(story_id)
    story.published = not story.published
    db.session.commit()

    return redirect(url_for("manage_stories"))


# ============================================================
# ADMIN — DELETE COMMENT
# ============================================================

@app.route("/admin/comments/delete/<int:comment_id>", methods=["POST"])
def delete_comment(comment_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()

    return redirect(request.referrer or url_for("dashboard"))


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

with app.app_context():
    db.create_all()


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"

    app.run(host="0.0.0.0", port=port, debug=debug_mode)