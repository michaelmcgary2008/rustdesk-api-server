"""Project-level HTTP middleware."""


class NormalizeDoubleApiPrefixMiddleware:
    """
    Collapse accidental /api/api/... to /api/...

    The RustDesk client builds URLs as ``{api-server}/api/heartbeat`` (see
    upstream ``hbbs_http/sync.rs``), so a stored api-server value that already
    ends in ``/api`` doubles the prefix and every request 404s. Rewriting here
    lets misconfigured clients keep working without touching each machine.

    Django resolves URLs from ``request.path_info`` (captured in
    ``WSGIRequest.__init__``), so that attribute must be rewritten —
    mutating ``META['PATH_INFO']`` alone has no effect on routing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_info = request.path_info
        if path_info.startswith('/api/api/'):
            new_path = path_info[len('/api'):]
            request.path = request.path[:len(request.path) - len(path_info)] + new_path
            request.path_info = new_path
            request.META['PATH_INFO'] = new_path
        return self.get_response(request)
