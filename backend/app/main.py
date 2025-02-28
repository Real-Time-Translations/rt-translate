from fastapi import FastAPI

app = FastAPI(title="Real-Time Translation API")

#test git working 3
@app.get("/")
async def root():
    return {"message": "API is running"}

