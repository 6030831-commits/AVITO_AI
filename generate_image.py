from openai import OpenAI
from datetime import datetime
import base64

client = OpenAI()

# Спрашиваем описание прямо в терминале
prompt = input("Опишите картинку: ")

# Спрашиваем качество, но можно просто нажать Enter — будет low
quality = input("Качество (low / medium / high) [Enter = low]: ")
if quality == "":
    quality = "low"

result = client.images.generate(
    model="gpt-image-2",
    prompt=prompt,
    size="1024x1024",
    quality=quality,
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

# Имя файла с датой и временем: image_2026-05-27_14-30-05.png
filename = "image_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"

with open(filename, "wb") as f:
    f.write(image_bytes)

print("Готово, сохранил в", filename)
