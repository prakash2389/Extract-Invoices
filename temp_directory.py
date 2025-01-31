import os
def temp_directory(temp_path, uploaded_file):
    if uploaded_file is not None:
        # Save the file to a temporary location
        temp_file_path = os.path.join(temp_path, uploaded_file.name)

        # Ensure the directory exists
        os.makedirs(temp_path, exist_ok=True)

        # Write the file to disk
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Now you can use temp_file_path for other operations
        return temp_file_path
