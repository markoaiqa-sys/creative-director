with open('frontend/app-reels.js', 'r', encoding='utf-8') as f:
    append_content = f.read()

with open('frontend/app.js', 'a', encoding='utf-8') as f:
    f.write('\n' + append_content)

print('SUCCESS')
