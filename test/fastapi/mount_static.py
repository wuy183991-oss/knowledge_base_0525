
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).parent
print(BASE_DIR)
static_dir = BASE_DIR / "static"

print(static_dir)

app = FastAPI()

#挂载前端资源
app.mount("/static",StaticFiles(directory=str(static_dir)),name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)