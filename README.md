# 🤖 AI Resume Analyzer & LinkedIn Scraper

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.48.1-red.svg)](https://streamlit.io/)
[![Groq](https://img.shields.io/badge/Groq-LLaMA3-green.svg)](https://console.groq.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent web application that combines **AI-powered resume analysis** with **automated LinkedIn job scraping**. This comprehensive tool helps job seekers gain deep insights into their resumes while simultaneously discovering relevant job opportunities.

## ✨ Features

### 📄 **Resume Analysis**
- **📊 Comprehensive Analysis** - Strengths, weaknesses, and improvement suggestions
- **📋 Summary Generation** - Quick overview of your resume
- **💡 Job Title Recommendations** - Personalized job suggestions
- **🎯 AI-Powered Insights** - Using Groq's LLaMA 3 model

### 🔍 **LinkedIn Scraper**
- **🤖 Automated Job Search** - No manual browsing needed
- **📊 Rich Data Extraction** - Company, title, location, description
- **🔗 Direct Application Links** - Ready to apply
- **🌍 Location-Based Search** - Find jobs in your area

## 🛠️ Technology Stack

### **Frontend & Web Framework**
- **Streamlit** - Modern web application framework
- **Streamlit Option Menu** - Enhanced navigation components
- **Streamlit Extras** - Additional UI components

### **AI & Machine Learning**
- **LangChain** - LLM-powered application framework
- **Groq API** - Ultra-fast inference API (LLaMA 3 8B model)
- **HuggingFace Transformers** - State-of-the-art NLP models
- **Sentence Transformers** - Advanced text embedding
- **FAISS** - High-performance vector similarity search

### **Data Processing & Analysis**
- **Pandas** - Data manipulation and analysis
- **NumPy** - Scientific computing
- **PyPDF2** - PDF text extraction
- **RAG Pipeline** - Retrieval-Augmented Generation

### **Web Automation & Scraping**
- **Selenium WebDriver** - Automated browser control
- **Chrome WebDriver** - Browser automation
- **WebDriver Manager** - Automatic driver management

## 🚀 Quick Start

### **Option 1: One-Click Setup (Windows)**
```bash
# 1. Clone the repository
git clone https://github.com/yourusername/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer

# 2. Double-click setup.bat to install dependencies
# 3. Double-click start.bat to run the app
# 4. Open http://localhost:8501 in your browser
```

### **Option 2: Manual Setup**
```bash
# 1. Clone the repository
git clone https://github.com/yourusername/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python -m streamlit run app.py

# 4. Open http://localhost:8501 in your browser
```

### **Option 3: Status Check**
```bash
# Check if everything is installed correctly
python check_status.py
```

## 📋 Prerequisites

- **Python 3.8+** installed on your system
- **Groq API Key** (free from [https://console.groq.com/](https://console.groq.com/))
- **PDF Resume** for analysis
- **Internet connection** for LinkedIn scraping

## 🔑 Getting Groq API Key

1. Visit [https://console.groq.com/](https://console.groq.com/)
2. Sign up for a free account
3. Create an API key in the dashboard
4. Use the key in the application

## �� Project Structure

```
AI-Resume-Analyzer/
├── 🚀 app.py                 # Main application (690 lines)
├── 📋 requirements.txt       # Python dependencies
├── ⚡ start.bat             # One-click run script (Windows)
├── 🛠️ setup.bat            # One-click install script (Windows)
├── 🔍 check_status.py       # Dependency checker
├── 📄 demo_resume.txt       # Sample resume for testing
├── 📖 README.md             # This file
└── 🚫 .gitignore            # Git ignore rules
```

## 🎯 How It Works

### **Resume Analysis Pipeline**
```
PDF Resume → Text Extraction → AI Analysis → Insights
```

1. **Upload PDF Resume** → User uploads their resume
2. **Text Extraction** → PyPDF2 extracts text from PDF
3. **Text Chunking** → LangChain splits text into manageable chunks
4. **AI Processing** → Groq LLM analyzes the content
5. **Results** → Returns comprehensive analysis

### **LinkedIn Scraping Pipeline**
```
Job Search → Web Scraping → Data Processing → Results
```

1. **User Input** → Job title, location, number of jobs
2. **URL Building** → Creates LinkedIn search URL
3. **Web Scraping** → Selenium automates browser to scrape data
4. **Data Extraction** → Gets company names, job titles, descriptions
5. **Results Display** → Shows formatted job listings

## 🔧 Configuration

### **Environment Variables**
Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key_here
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token_here
```

### **Customization**
- Modify `app.py` to change AI prompts
- Update `requirements.txt` for different dependencies
- Customize UI in Streamlit components

## 🤝 Contributing

We welcome contributions! Please feel free to submit a Pull Request.

### **Development Setup**
```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/yourusername/AI-Resume-Analyzer.git

# 3. Create a feature branch
git checkout -b feature/amazing-feature

# 4. Make your changes
# 5. Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# 6. Open a Pull Request
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Groq** for providing ultra-fast LLM inference
- **Streamlit** for the amazing web framework
- **LangChain** for LLM orchestration tools
- **HuggingFace** for transformer models
- **Selenium** for web automation capabilities

## 📞 Support

If you encounter any issues or have questions:

1. **Check the documentation** in this README
2. **Run the status checker**: `python check_status.py`
3. **Open an issue** on GitHub
4. **Contact the maintainers**

## 🚀 Deployment

### **Streamlit Cloud**
1. Push your code to GitHub
2. Connect your repository to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy automatically

### **Local Deployment**
```bash
# Install dependencies
pip install -r requirements.txt

# Run with custom port
streamlit run app.py --server.port 8080
```

---

**⭐ Star this repository if you find it helpful!**

**🔗 Share with your network to help other job seekers!**

