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
            
    <style>

      .try-out, .execute-wrapper, .btn.try-out__btn {
        display: none !important;
      }

      body {
        margin: 0;
        background: #f5f5f5;
      }
      .topbar-wrapper {
        background: #2c3e50;
      }
      .github-link {
        padding: 10px;
        background-color: #eaf2ff;
        font-family: sans-serif;
        font-size: 14px;
        text-align: center;
      }
      .github-link a {
        color: #0366d6;
        text-decoration: none;
        font-weight: bold;
      }
    
    </style>
  </head>
  <body>
    <div class="github-link">
      👉 View this project on <a href="https://github.com/Godspeed-exe/heron-cardano" target="_blank">GitHub</a>
    </div>
            
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        SwaggerUIBundle({ url: "openapi.json", dom_id: "#swagger-ui",  supportedSubmitMethods: [] });
      };
    </script>
  </body>
</html>
""")