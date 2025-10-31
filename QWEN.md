# Qwen Setup Guide

This directory contains the configuration file for Qwen's MCP (Model Context Protocol) integration.

## Configuration Location

The Qwen configuration file is located at `.qwen/settings.json` in this repository.

## Setup Instructions

1. Create a symlink from your Qwen configuration directory to this repository:
   ```bash
   ln -s ~/path/to/agents-environment-config/.qwen/settings.json ~/.qwen/settings.json
   ```

2. Update the API keys in `.qwen/settings.json` with your actual credentials:
   - `CONTEXT7_API_KEY`: Your Context7 API key
   - `STRIPE_SECRET_KEY`: Your Stripe secret key
   - `BROWSERBASE_API_KEY`: Your Browserbase API key
   - `BROWSERBASE_PROJECT_ID`: Your Browserbase project ID
   - `OPENAI_API_KEY`: Your OpenAI API key (for brain-trust-ask-mcp)
   - `POSTHOG_AUTH_HEADER`: Your PostHog authentication header
   - `PACKAGES_API_AUTH_TOKEN`: Your packages API authentication token

3. Restart Qwen to load the new configuration.

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

If Qwen is not recognizing the MCP servers:

1. Verify the symlink is correctly created: `ls -la ~/.qwen/settings.json`
2. Check that the JSON syntax is valid
3. Ensure all required API keys are filled in
4. Restart Qwen completely
5. Check Qwen logs for any MCP connection errors

## Additional Resources

- [Qwen Documentation](https://qwenlm.com/docs)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
