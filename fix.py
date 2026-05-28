import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the first occurrence of </body>
idx = content.find('</body>')
if idx != -1:
    content = content[:idx] + '</body>\n</html>\n'

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('SUCCESS')
