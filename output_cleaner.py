import re

def clean_terminal_output(input_file, output_file):
    # Read the messy file
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Strip ANSI escape codes (the color codes like \x1b[35m)
    # This regex catches standard terminal color formatting
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    
    # 2. Remove box drawing characters
    text = re.sub(r'[╭─╮│╰╯]', '', text)

    # 3. Remove the tags
    text = re.sub(r'\\', '', text)

    # 4. Clean up the messy line spacing left behind by the boxes
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Strip trailing/leading whitespace from the line
        line = line.strip()
        cleaned_lines.append(line)

    # Rejoin the text, replacing 3 or more consecutive empty lines with just 2
    # to maintain clear paragraph spacing without massive gaps.
    final_text = '\n'.join(cleaned_lines)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)

    # Write to the new clean file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_text)
    
    print(f"Cleaning complete! Saved to {output_file}")

# Run the function
# Replace 'output_20260429_010402.txt' with your actual file name
input_filename = 'output_3.txt'
output_filename = 'cleaned_negotiation_log3.txt'

clean_terminal_output(input_filename, output_filename)