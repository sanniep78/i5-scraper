"""
Rate limiting and authentication for scraper endpoint
"""

import time
from functools import wraps
from flask import request, jsonify
import hashlib
import os


class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.cleanup_interval = 3600  # Clean up old entries every hour
        self.last_cleanup = time.time()

    def is_allowed(self, identifier, max_requests=5, window_seconds=3600):
        """Check if request is allowed based on rate limit"""
        current_time = time.time()

        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup(current_time)

        # Get request history for this identifier
        if identifier not in self.requests:
            self.requests[identifier] = []

        # Remove requests outside the time window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < window_seconds
        ]

        # Check if limit exceeded
        if len(self.requests[identifier]) >= max_requests:
            return False

        # Add current request
        self.requests[identifier].append(current_time)
        return True

    def _cleanup(self, current_time):
        """Remove old entries from memory"""
        for identifier in list(self.requests.keys()):
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if current_time - req_time < self.cleanup_interval
            ]
            if not self.requests[identifier]:
                del self.requests[identifier]
        self.last_cleanup = current_time

    def get_reset_time(self, identifier, window_seconds=3600):
        """Get time until rate limit resets"""
        if identifier not in self.requests or not self.requests[identifier]:
            return 0

        oldest_request = min(self.requests[identifier])
        reset_time = oldest_request + window_seconds
        return max(0, int(reset_time - time.time()))


# Global rate limiter instance
rate_limiter = RateLimiter()


def require_api_key(f):
    """Decorator to require API key for endpoint"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        expected_key = os.environ.get('API_KEY')

        # If no API key is configured, allow access (for local dev)
        if not expected_key:
            return f(*args, **kwargs)

        if not api_key or api_key != expected_key:
            return jsonify({
                'success': False,
                'error': 'Invalid or missing API key'
            }), 401

        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests=5, window_seconds=3600):
    """Decorator to rate limit endpoint"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use IP address as identifier
            identifier = request.remote_addr

            if not rate_limiter.is_allowed(identifier, max_requests, window_seconds):
                reset_time = rate_limiter.get_reset_time(identifier, window_seconds)
                return jsonify({
                    'success': False,
                    'error': f'Rate limit exceeded. Try again in {reset_time} seconds.',
                    'reset_in_seconds': reset_time
                }), 429

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def simple_auth(f):
    """Simple password protection"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        password = request.headers.get('X-Password') or request.args.get('password')
        expected_password = os.environ.get('SCRAPER_PASSWORD')

        # If no password is configured, allow access (for local dev)
        if not expected_password:
            return f(*args, **kwargs)

        if not password or password != expected_password:
            return jsonify({
                'success': False,
                'error': 'Invalid or missing password'
            }), 401

        return f(*args, **kwargs)
    return decorated_function
