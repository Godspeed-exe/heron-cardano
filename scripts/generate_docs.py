import requests
import os

os.makedirs("docs", exist_ok=True)

response = requests.get("http://localhost:8001/openapi.json")
with open("docs/openapi.json", "w") as f:
    f.write(response.text)

with open("docs/index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
  <head>
    <title>Heron API Docs</title>
    <link href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" rel="stylesheet" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        SwaggerUIBundle({ url: "openapi.json", dom_id: "#swagger-ui" });
      };
    </script>
  </body>
</html>
""")