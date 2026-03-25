
with open('app.py', 'r') as f:
    content = f.read()

# Remove the run block from middle
run_block = "\n# ─── Run ─────────────────────────────────────────────────────────────────────\nif __name__ == \"__main__\":\n    app.run(debug=True, port=5000)\n"
content = content.replace(run_block, "\n")

# Append it at the very end
content = content.rstrip() + "\n\n# ─── Run ─────────────────────────────────────────────────────────────────────\nif __name__ == \"__main__\":\n    app.run(debug=True, port=5000)\n"

with open('app.py', 'w') as f:
    f.write(content)
print("Done")
