// Filebase Uploader for DoctorLink Waitlist
// Uses AWS SDK v3 with encoded credentials (for demo purposes only)

const FILEBASE_CREDS = {
    accessKey: atob('NzgzMTk0QjA1MEUxNjIyODkxOUU='),
    secretKey: atob('Sk1leHlBbFFkaXVUdFVCTml4SVN5TFFkQXppUUlyZ1YxdThHeTF2eQ==')
};

let s3Client = null;

// Load AWS SDK and initialize
async function initS3() {
    if (s3Client) return s3Client;
    
    // Dynamically load AWS SDK bundle
    await new Promise((resolve, reject) => {
        if (window.AWS) {
            resolve();
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/aws-sdk@2.1360.0/dist/aws-sdk.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
    
    // Configure AWS for Filebase
    AWS.config.update({
        region: 'us-east-1',
        accessKeyId: FILEBASE_CREDS.accessKey,
        secretAccessKey: FILEBASE_CREDS.secretKey
    });
    
    // Use S3 with custom endpoint
    s3Client = new AWS.S3({
        endpoint: 'https://s3.filebase.com',
        signatureVersion: 'v4',
        s3ForcePathStyle: true // Required for Filebase
    });
    
    console.log('S3 Client initialized for Filebase');
    return s3Client;
}

// Upload to Filebase
async function uploadToFilebase(data, role, email) {
    const client = await initS3();
    
    const key = `waitlist/${role.toUpperCase()}/${email.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.json`;
    
    const params = {
        Bucket: 'skyhealth',
        Key: key,
        Body: JSON.stringify({
            ...data,
            submitted_at: new Date().toISOString(),
            source: 'github_pages_waitlist'
        }),
        ContentType: 'application/json'
    };
    
    return new Promise((resolve, reject) => {
        client.upload(params, function(err, data) {
            if (err) {
                console.error('S3 upload error:', err);
                reject(err);
            } else {
                console.log('Uploaded to:', data.Location);
                resolve(data.Location);
            }
        });
    });
}

// Export for use
window.FilebaseUploader = { uploadToFilebase, initS3 };