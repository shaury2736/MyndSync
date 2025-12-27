# NoteStack Project Documentation

## Project Overview
NoteStack is a specialized academic resource management platform developed specifically for the student community at Madhav Institute of Technology and Science (MITS). The platform serves as a centralized digital repository for academic materials, including lecture notes and previous year questions (PYQs). By integrating advanced artificial intelligence and cloud infrastructure, NoteStack transforms static study materials into interactive learning resources.

## Core Functionality
The platform is built around several key functional areas:

### 1. Authentication and Identity Management
NoteStack utilizes Firebase Authentication to ensure that only verified students can access the platform's resources. The system strictly enforces institutional email validation, requiring users to register with a domain ending in @mitsgwl.ac.in. This ensures a secure, private community environment.

### 2. Resource Management and Uploads
Students can contribute to the platform by uploading Notes or PYQs. The system handles file uploads securely, storing the physical files in Google Cloud Storage and indexing the metadata in Cloud Firestore. A specific naming convention is enforced to maintain organization: [Subject]_[Department]_[EnrollmentID].pdf.

### 3. AI-Powered Academic Assistance 
The platform leverages Google Gemini models to provide intelligent study tools:
- **Abstractive Summarization**: Large academic documents are processed to generate both concise and detailed summaries, helping students grasp core concepts quickly.
- **Automated Question Generation**: The system can analyze document text to produce practice examination questions in both objective (multiple-choice) and subjective formats.

### 4. Personal Library and Tracking
Users have a dedicated "My Library" section where they can save documents shared by others. The "My Uploads" section allows users to manage their own contributions. The platform also tracks material "Views" to provide engagement analytics on the user dashboard.

## Technical Architecture

### Backend Framework
- **Flask (Python)**: The primary web server handling routing, session management, and API integrations.

### Database and Infrastructure (Firebase)
- **Cloud Firestore**: A NoSQL document database used for storing user profiles, document metadata, and activity logs.
- **Cloud Storage**: Secure persistent storage for academic PDFs and user media.
- **Firebase Admin SDK**: Server-side integration for secure data and auth management.

### Artificial Intelligence
- **Google Generative AI (Gemini Flash/Pro)**: Utilized for natural language processing, text extraction analysis, and generative study tools.

### Frontend Implementation
- **Standard Web Technologies**: Vanilla HTML5, CSS3, and JavaScript (ES6).
- **Responsive Design**: A custom CSS grid and flexbox system designed for both mobile and desktop academic use.
- **Google Fonts**: Integration of the 'Outfit' font family for a clean, premium reading experience.

## Module Structure
- **app.py**: The central entry point of the application, managing all Flask routes and service initializations.
- **modules/utils.py**: Utility functions for file sanitization, filename generation, and text extraction from varying formats (PDF/DOCX).
- **modules/summary.py**: Dedicated interface for interacting with Gemini models for summarization tasks.
- **modules/questions.py**: Logic for prompting AI models to generate structured examination questions.
- **static/js/firebase_config.js**: Client-side initialization of Firebase services for tracking and dynamic UI updates.

## Setup and Installation
To deploy a local instance of NoteStack:

1. Clone the repository to your local machine.
2. Install the required Python dependencies: `pip install -r requirements.txt`.
3. Set up the .env file with appropriate credentials:
   - `GEMINI_API_KEY`: Required for AI functionality.
   - Firebase Service Account JSON path.
4. Initialize the Flask server: `python app.py`.

## Academic Integrity and Safety
NoteStack is designed with safety in mind. The platform includes logic for content verification and uploader tracking to maintain a high standard of academic resources.
