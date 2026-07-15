"""
Automated database initialization script for PieFed Docker deployment.

This script:
1. Creates the Flask app context
2. Checks if the database has been initialized
3. If not initialized, seeds the database and creates an admin user
4. If already initialized, does nothing (idempotent)

Environment variables for admin user creation:
    ADMIN_USERNAME  - Admin username (default: admin)
    ADMIN_EMAIL     - Admin email (optional)
    ADMIN_PASSWORD  - Admin password (default: generates a random one and prints it)
"""

import json
import logging
import os
import random
import secrets
import string
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Ensure we can import from the app directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_APP"] = "pyfedi.py"


def main():
    from app import create_app, db
    from app.activitypub.signature import RsaKeys
    from app.utils import retrieve_block_list, retrieve_peertube_block_list
    from app.models import (
        BannedInstances,
        CronJobLog,
        Domain,
        Instance,
        Language,
        Role,
        RolePermission,
        Settings,
        Site,
        User,
    )
    from flask_migrate import Migrate
    from sqlalchemy import text

    app = create_app()
    Migrate(app, db)

    with app.app_context():
        inspector = db.inspect(db.engine)

        # Check if already fully initialized (has admin user)
        try:
            if User.query.first():
                logger.info("✅ Database already initialized with admin user. Skipping.")
                return
        except Exception:
            # Tables may not exist yet, that's fine
            pass

        logger.info("🔄 Initializing/repairing database...")

        # Ensure tables exist (idempotent if flask db upgrade already ran)
        db.create_all()

        # Drop PostgreSQL functions that might cause errors
        db.session.execute(
            text("DROP FUNCTION IF EXISTS post_search_vector_update() CASCADE")
        )
        db.session.commit()

        db.configure_mappers()
        db.create_all()

        # Seed initial data only if not already present
        if not Site.query.first():
            private_key, public_key = RsaKeys.generate_keypair()
            db.session.add(
                Site(
                    name="PieFed",
                    description="Explore Anything, Discuss Everything.",
                    public_key=public_key,
                    private_key=private_key,
                    language_id=2,
                )
            )
        if not Instance.query.first():
            db.session.add(Instance(domain=app.config["SERVER_NAME"], software="PieFed"))
        if not Settings.query.first():
            db.session.add(Settings(name="allow_nsfw", value=json.dumps(False)))
            db.session.add(Settings(name="allow_nsfl", value=json.dumps(False)))
            db.session.add(Settings(name="allow_dislike", value=json.dumps(True)))
            db.session.add(Settings(name="allow_local_image_posts", value=json.dumps(True)))
            db.session.add(Settings(name="allow_remote_image_posts", value=json.dumps(True)))
            db.session.add(Settings(name="federation", value=json.dumps(True)))
        banned_instances = [
            "anonib.al",
            "lemmygrad.ml",
            "gab.com",
            "rqd2.net",
            "exploding-heads.com",
            "hexbear.net",
            "hilariouschaos.com",
            "threads.com",
            "noauthority.social",
            "pieville.net",
            "links.hackliberty.org",
            "poa.st",
            "freespeechextremist.com",
            "bae.st",
            "nicecrew.digital",
            "detroitriotcity.com",
            "gregtech.eu",
            "pawoo.net",
            "shitposter.club",
            "spinster.xyz",
            "catgirl.life",
            "gameliberty.club",
            "yggdrasil.social",
            "beefyboys.win",
            "brighteon.social",
            "cum.salon",
            "wizard.casa",
            "maga.place",
            "lemmychan.org",
        ]
        for bi in banned_instances:
            db.session.add(BannedInstances(domain=bi))

        # Load initial domain block list
        block_list = retrieve_block_list()
        if block_list:
            for domain in block_list.split("\n"):
                db.session.add(Domain(name=domain.strip(), banned=True))

        # Load peertube domain block list
        block_list = retrieve_peertube_block_list()
        if block_list:
            for domain in block_list.split("\n"):
                db.session.add(Domain(name=domain.strip(), banned=True))
                db.session.add(BannedInstances(domain=domain.strip()))

        # Initial languages
        db.session.add(Language(name="Undetermined", code="und"))
        db.session.add(Language(code="en", name="English"))
        db.session.add(Language(code="de", name="Deutsch"))
        db.session.add(Language(code="es", name="Español"))
        db.session.add(Language(code="fi", name="Finnish"))
        db.session.add(Language(code="fr", name="Français"))
        db.session.add(Language(code="hi", name="हिन्दी"))
        db.session.add(Language(code="ja", name="日本語"))
        db.session.add(Language(code="zh", name="中文"))
        db.session.add(Language(code="pl", name="Polski"))
        db.session.add(Language(code="uk", name="Українська"))

        # Seed roles only if not already present
        if not Role.query.first():
            anon_role = Role(name="Anonymous user", weight=0)
            db.session.add(anon_role)

            auth_role = Role(name="Authenticated user", weight=1)
            db.session.add(auth_role)

            staff_role = Role(name="Staff", weight=2)
            staff_role.permissions.append(RolePermission(permission="approve registrations"))
            staff_role.permissions.append(RolePermission(permission="ban users"))
            staff_role.permissions.append(RolePermission(permission="administer all communities"))
            staff_role.permissions.append(RolePermission(permission="administer all users"))
            db.session.add(staff_role)

            admin_role = Role(name="Admin", weight=3)
            admin_role.permissions.append(RolePermission(permission="approve registrations"))
            admin_role.permissions.append(RolePermission(permission="change user roles"))
            admin_role.permissions.append(RolePermission(permission="ban users"))
            admin_role.permissions.append(RolePermission(permission="manage users"))
            admin_role.permissions.append(RolePermission(permission="change instance settings"))
            admin_role.permissions.append(RolePermission(permission="administer all communities"))
            admin_role.permissions.append(RolePermission(permission="administer all users"))
            admin_role.permissions.append(RolePermission(permission="edit cms pages"))
            db.session.add(admin_role)

        # Add cron jobs to db (only if not already present)
        existing_cron = {c.name for c in CronJobLog.query.all()}
        cron_jobs = [
            ("send_missed_notifs", timedelta(hours=7)),
            ("process_email_bounces", timedelta(hours=7)),
            ("clean_up_old_activities", timedelta(hours=7)),
            ("remove_orphan_files", timedelta(days=8)),
            ("daily_maintenance", timedelta(hours=25)),
            ("send_queue", timedelta(minutes=5)),
        ]
        for name, freq in cron_jobs:
            if name not in existing_cron:
                db.session.add(CronJobLog(name=name, frequency=freq))

        db.session.commit()
        logger.info("✅ Database schema and initial data created.")

        # Create admin user
        _create_admin_user(app)


def _create_admin_user(app):
    """Create an admin user from environment variables."""
    from app import db
    from app.activitypub.signature import RsaKeys
    from app.models import Role, User
    from app.utils import gibberish

    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()

    with app.app_context():
        existing = User.query.filter(User.id == 1).first()
        if existing:
            logger.info(
                f"✅ Admin user '{existing.user_name}' already exists. Skipping creation."
            )
            return

        if not admin_username:
            admin_username = "admin"
            logger.warning(
                f"⚠️  ADMIN_USERNAME not set. Using default: '{admin_username}'"
            )

        if not admin_password:
            admin_password = "".join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
            )
            logger.warning("⚠️  ADMIN_PASSWORD not set. Generated random password.")
            logger.warning(f"⚠️  IMPORTANT: Save this password immediately!")
            logger.warning(f"⚠️  Admin password: {admin_password}")

        admin_role = Role.query.filter(Role.name == "Admin").first()
        if not admin_role:
            logger.error(
                "❌ Admin role not found in database! Cannot create admin user."
            )
            return

        private_key, public_key = RsaKeys.generate_keypair()

        admin_user = User(
            user_name=admin_username,
            title=admin_username,
            email=admin_email,
            instance_id=1,
            email_unread_sent=False,
            verified=True,
            private_key=private_key,
            public_key=public_key,
            alt_user_name=gibberish(random.randint(8, 20)),
            last_seen=datetime.utcnow(),
        )
        admin_user.set_password(admin_password)
        admin_user.roles.append(admin_role)

        server_name = app.config.get("SERVER_NAME", "localhost")
        server_url = f"{app.config.get('HTTP_PROTOCOL', 'https')}://{server_name}"

        admin_user.ap_profile_id = f"{server_url}/u/{admin_user.user_name.lower()}"
        admin_user.ap_public_url = f"{server_url}/u/{admin_user.user_name}"
        admin_user.ap_inbox_url = f"{server_url}/u/{admin_user.user_name.lower()}/inbox"

        db.session.add(admin_user)
        db.session.commit()

        logger.info(f"✅ Admin user '{admin_username}' created successfully!")
        if admin_email:
            logger.info(f"   Email: {admin_email}")
        logger.info("   You can now log in and manage your instance.")


if __name__ == "__main__":
    main()
