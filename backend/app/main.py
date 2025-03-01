from fastapi import FastAPI

# test something
app = FastAPI(title="Real-Time Translation API")

#test git working 3
@app.get("/")
async def root():
    return {"message": "API is running"}

