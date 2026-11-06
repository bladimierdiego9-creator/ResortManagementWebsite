from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # use_reloader=False prevents the reloader from spawning a second process
    # which loses the SQLAlchemy engine event listeners before create_all runs
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
