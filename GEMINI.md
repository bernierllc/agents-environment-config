# Gemini Setup Guide

This directory contains the configuration file for Google Gemini's MCP (Model Context Protocol) integration.

## Configuration Location

The Gemini configuration file is located at `.gemini/settings.json` in this repository.

## Setup Instructions

1. Create a symlink from your Gemini configuration directory to this repository:
   ```bash
   ln -s ~/path/to/agents-environment-config/.gemini/settings.json ~/.gemini/settings.json
   ```

2. Update the API keys in `.gemini/settings.json` with your actual credentials:
   - `CONTEXT7_API_KEY`: Your Context7 API key
   - `STRIPE_SECRET_KEY`: Your Stripe secret key
   - `BROWSERBASE_API_KEY`: Your Browserbase API key
   - `BROWSERBASE_PROJECT_ID`: Your Browserbase project ID
   - `OPENAI_API_KEY`: Your OpenAI API key (for brain-trust-ask-mcp)
   - `POSTHOG_AUTH_HEADER`: Your PostHog authentication header
   - `PACKAGES_API_AUTH_TOKEN`: Your packages API authentication token

3. Restart Gemini to load the new configuration.

## MCP Servers Configured

This configuration includes the following MCP servers:

- **vibe-kanban**: Kanban project management
- **Supabase**: Database and backend services
- **context7**: Library documentation
- **Semgrep**: Code security scanning
- **Stripe**: Payment processing
- **Figma**: Design collaboration
- **Browserbase**: Browser automation
- **playwright**: UI testing framework
- **brain-trust-ask-mcp**: AI-powered assistance
- **packages-api**: Internal packages API
- **PostHog**: Product analytics
- **Vercel**: Deployment platform

## Troubleshooting

If Gemini is not recognizing the MCP servers:

1. Verify the symlink is correctly created: `ls -la ~/.gemini/settings.json`
2. Check that the JSON syntax is valid
3. Ensure all required API keys are filled in
4. Restart Gemini completely
5. Check Gemini logs for any MCP connection errors

## Additional Resources

- [Gemini Documentation](https://gemini.google.com/docs)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
