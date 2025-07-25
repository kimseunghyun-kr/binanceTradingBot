import uvicorn

if __name__ == "__main__":
    # Set the profile as needed (default to development if not set)
    uvicorn.run("KwontBot:app", host="127.0.0.1", port=8000, reload=True, lifespan="on")
