# Troubleshooting Standards

## Error Investigation

### Browser Errors
When a browser error is shared (console or copied):
1. **Check logs**: Refer to `./logs/frontend.log` for frontend errors
2. **Check console**: Review browser console for errors
3. **Check network**: Review network tab for failed requests
4. **Reproduce**: Attempt to reproduce the error locally

### Frontend Logs
- Check `logs/frontend.log` for detailed error information
- Review error stack traces
- Check for related errors around the same time
- Look for patterns in error messages

## Debugging Workflow

### 1. Reproduce the Issue
- Reproduce locally if possible
- Check if issue is environment-specific
- Verify steps to reproduce

### 2. Gather Information
- Error messages and stack traces
- Browser console logs
- Network request logs
- Server logs (if applicable)
- User actions leading to error

### 3. Investigate Root Cause
- Check code changes related to error
- Review recent deployments
- Check database state
- Verify environment configuration

### 4. Fix and Verify
- Implement fix
- Test fix locally
- Verify fix in staging
- Monitor production after deployment

## Common Issues

### Frontend Errors
- Check `logs/frontend.log` first
- Review browser console
- Check network requests
- Verify API responses

### Backend Errors
- Check server logs
- Review database logs
- Check API endpoint logs
- Verify error handling

### Database Issues
- Check connection status
- Review query logs
- Verify migrations
- Check database state

## Debugging Tools

### Frontend
- Browser DevTools
- React DevTools
- Network tab
- Console logs

### Backend
- Server logs
- Database logs
- API logs
- Error tracking (Sentry, etc.)

## References
- **Error Handling**: See `topics/quality/error-handling.mdc`
- **Logging**: See `topics/quality/logging.mdc`
- **Observability**: See `topics/observability/monitoring.mdc`
