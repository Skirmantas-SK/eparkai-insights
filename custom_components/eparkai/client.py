"""Cookie-aware website client; all calls run in Home Assistant's executor."""

from html.parser import HTMLParser
import requests

from .production import ParseError, parse_intervals

BASE_URL = "https://www.eparkai.lt"


class AuthenticationError(Exception):
    """Login or interactive account confirmation is required."""


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {}
        elif tag == "input" and self.current is not None and attrs.get("name"):
            self.current[attrs["name"]] = attrs.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None

    def find(self, form_id):
        matches = [form for form in self.forms if form.get("form_id") == form_id]
        return matches[0] if len(matches) == 1 else None


class EParkaiClient:
    def __init__(self, username, password, client_id, session=None):
        self.username, self.password = username, password
        self.url = f"{BASE_URL}/user/{client_id}/generation"
        self.login_url = f"{BASE_URL}/user/login?destination=/user/{client_id}/generation"
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({"User-Agent": "HomeAssistant-eParkai/0.1"})
        self.auth_failed = False

    def _request(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=(10, 30), **kwargs)
        if response.status_code in (401, 403) or (300 <= response.status_code < 400):
            raise AuthenticationError("Session expired")
        response.raise_for_status()
        return response

    def _generation_form(self):
        response = self._request("GET", self.url)
        return Forms(response.text).find("product_generation_form")

    def fetch(self, plant_id, address, now):
        if self.auth_failed:
            raise AuthenticationError("Reauthentication required")
        try:
            form = self._generation_form()
            if form is None:
                response = self._request("GET", self.login_url)
                fields = Forms(response.text).find("user_login_form")
                if fields is None:
                    raise AuthenticationError("Login form missing")
                fields.update(name=self.username, **{"pass": self.password, "login_type": "1"})
                response = self._request("POST", self.login_url, data=fields)
                if Forms(response.text).find("product_generation_form") is None:
                    raise AuthenticationError("Check credentials and portal contact confirmation")
                form = self._generation_form()
                if form is None:
                    raise AuthenticationError("Generation form missing")
            fields = {key: form[key] for key in ("form_id", "form_build_id", "form_token") if key in form}
            fields.update(period="week", current_date=now.strftime("%Y-%m-%d"),
                          generation_electricity=plant_id, _drupal_ajax="1",
                          _triggering_element_name="period")
            if address:
                fields["address"] = address
            response = self._request(
                "POST", self.url + "?ajax_form=1&_wrapper_format=drupal_ajax",
                data=fields, headers={"X-Requested-With": "XMLHttpRequest"}, allow_redirects=False,
            )
            if Forms(response.text).find("user_login_form") is not None:
                raise AuthenticationError("Session expired")
            try:
                payload = response.json()
            except ValueError as err:
                raise ParseError("Invalid generation JSON") from err
            return parse_intervals(payload)
        except AuthenticationError:
            self.auth_failed = True
            raise

    def close(self):
        self.session.close()
