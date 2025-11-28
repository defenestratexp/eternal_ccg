#!/home/tthompson/.virtualenvs/n9n/bin/python

import csv
import os
import re


# Function to parse each line of the deck file
def parse_deck_line(line):
    # Regular expression to match the deck card information
    match = re.match(r"(\d+) (.+?) (\*Premium\* )?\(Set(\d+) #(\d+)\)", line)
    if match:
        number_owned = match.group(1)
        card_name = match.group(2)
        premium = "Yes" if match.group(3) else "No"
        set_number = match.group(4)
        card_in_set = match.group(5)
        return [number_owned, card_name, premium, set_number, card_in_set]
    return None


# Function to convert deck text files to CSV
def convert_deck_to_csv(input_dir, output_dir):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Loop over all text files in the input directory
    for deck_file in os.listdir(input_dir):
        if deck_file.endswith(".txt"):
            deck_file_path = os.path.join(input_dir, deck_file)
            deck_name = os.path.splitext(deck_file)[0]
            output_file_path = os.path.join(output_dir, f"{deck_name}.csv")

            # Open the input deck text file and output CSV file
            with open(deck_file_path, "r") as infile, open(
                output_file_path, "w", newline=""
            ) as outfile:
                csv_writer = csv.writer(outfile)
                # Write the CSV header
                csv_writer.writerow(
                    [
                        "Number Owned",
                        "Card Name",
                        "Premium",
                        "Set Number",
                        "Card Number",
                    ]
                )

                # Read each line from the deck text file
                for line in infile:
                    # Parse the line and write it to the CSV if it's valid
                    card_info = parse_deck_line(line.strip())
                    if card_info:
                        csv_writer.writerow(card_info)

            print(
                f"Conversion complete for {deck_file}! The output is saved as {output_file_path}."
            )


# Example usage:
# Specify the input and output directories
input_directory = os.path.expanduser("~/games/eternal/deck_text")
output_directory = os.path.expanduser("~/games/eternal/deck_csv")

# Call the function to process all deck text files
convert_deck_to_csv(input_directory, output_directory)
