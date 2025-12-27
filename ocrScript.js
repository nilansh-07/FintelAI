
// ocrScript.js
const fs = require('fs');
const Groq = require('groq-sdk');

const groq = new Groq({
    apiKey: process.env.GROQ_API_KEY
});

// Function to encode image to base64
function encodeImage(filePath) {
    const fileBuffer = fs.readFileSync(filePath);
    return fileBuffer.toString('base64');
}

async function runOCR(filePath, prompt) {
    try {
        if (!process.env.GROQ_API_KEY) {
            throw new Error("GROQ_API_KEY is missing in environment variables.");
        }

        const base64Image = encodeImage(filePath);
        
        // Use meta-llama/llama-4-maverick-17b-128e-instruct (currently free on Groq)
        const chatCompletion = await groq.chat.completions.create({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt || "Extract all text from this image as structured JSON."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": `data:image/jpeg;base64,${base64Image}`
                            }
                        }
                    ]
                }
            ],
            "model": "meta-llama/llama-4-maverick-17b-128e-instruct", 
            "temperature": 0,
            "stream": false,
            "response_format": { "type": "json_object" } // Force JSON output
        });

        // Output ONLY the content for Python to capture
        console.log(chatCompletion.choices[0].message.content);

    } catch (error) {
        console.error("OCR Error:", error.message);
        process.exit(1);
    }
}

// Get arguments from Python
const filePath = process.argv[2];
const prompt = process.argv[3];

runOCR(filePath, prompt);