# Deploying the PII Masking Application to Vercel

This guide provides step-by-step instructions for deploying the PII Masking Application to Vercel.

## Prerequisites

1. A GitHub account
2. A Vercel account (you can sign up at [vercel.com](https://vercel.com) using your GitHub account)
3. Git installed on your local machine

## Deployment Steps

### 1. Push Your Code to GitHub

```bash
# Initialize a git repository if you haven't already
git init

# Add all files to git
git add .

# Commit the changes
git commit -m "Initial commit"

# Add your GitHub repository as a remote
git remote add origin https://github.com/yourusername/your-repo-name.git

# Push to GitHub
git push -u origin main
```

### 2. Deploy to Vercel

1. Log in to your Vercel account
2. Click on "New Project"
3. Import your GitHub repository
4. Vercel will automatically detect the project configuration
5. Click "Deploy"

Vercel will automatically build and deploy both the frontend and backend components of your application based on the configuration in `vercel.json`.

### 3. Environment Variables

If needed, you can set environment variables in the Vercel dashboard:

1. Go to your project settings
2. Navigate to the "Environment Variables" tab
3. Add any required environment variables

### 4. Verify Deployment

Once deployment is complete, Vercel will provide you with a URL for your application. Visit this URL to verify that your application is working correctly.

## Troubleshooting

### Common Issues

1. **Build Failures**: Check the build logs in the Vercel dashboard for specific error messages.

2. **API Connection Issues**: Ensure that your frontend is correctly configured to connect to the API endpoints.

3. **Missing Dependencies**: Verify that all required dependencies are listed in the `requirements.txt` file for the backend and `package.json` for the frontend.

### Getting Help

If you encounter issues with your deployment, you can:

- Check the Vercel documentation at [vercel.com/docs](https://vercel.com/docs)
- Visit the Vercel support forums
- Review the build logs in the Vercel dashboard for specific error messages