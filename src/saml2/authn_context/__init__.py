from saml2.saml import AuthnContext, AuthnContextClassRef
from saml2.samlp import RequestedAuthnContext

__author__ = 'rolandh'

import hashlib

from saml2 import extension_elements_to_elements

UNSPECIFIED = "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified"

INTERNETPROTOCOLPASSWORD = \
    'urn:oasis:names:tc:SAML:2.0:ac:classes:InternetProtocolPassword'
MOBILETWOFACTORCONTRACT = \
    'urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract'
PASSWORDPROTECTEDTRANSPORT = \
    'urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport'
PASSWORD = 'urn:oasis:names:tc:SAML:2.0:ac:classes:Password'
TLSCLIENT = 'urn:oasis:names:tc:SAML:2.0:ac:classes:TLSClient'

AL1 = "http://idmanagement.gov/icam/2009/12/saml_2.0_profile/assurancelevel1"
AL2 = "http://idmanagement.gov/icam/2009/12/saml_2.0_profile/assurancelevel2"
AL3 = "http://idmanagement.gov/icam/2009/12/saml_2.0_profile/assurancelevel3"
AL4 = "http://idmanagement.gov/icam/2009/12/saml_2.0_profile/assurancelevel4"

from saml2.authn_context import ippword
from saml2.authn_context import mobiletwofactor
from saml2.authn_context import ppt
from saml2.authn_context import pword
from saml2.authn_context import sslcert

CMP_TYPE = ['exact', 'minimum', 'maximum', 'better']


class AuthnBroker(object):
    def __init__(self):
        self.db = {"info": {}, "key": {}}

    def exact(self, a, b):
        return a == b

    def minimum(self, a, b):
        return b >= a

    def maximum(self, a, b):
        return b <= a

    def better(self, a, b):
        return b > a

    def add(self, spec, method, level=0, authn_authority=""):
        """
        Adds a new authentication method.
        Assumes not more than one authentication method per AuthnContext
        specification.

        :param spec: What the authentication endpoint offers in the form
            of an AuthnContext
        :param method: A identifier of the authentication method.
        :param level: security level, positive integers, 0 is lowest
        :return:
        """

        if spec.authn_context_class_ref:
            key = spec.authn_context_class_ref.text
            _info = {
                "class_ref": key,
                "method": method,
                "level": level,
                "authn_auth": authn_authority
            }
        elif spec.authn_context_decl:
            key = spec.authn_context_decl.c_namespace
            _info = {
                "method": method,
                "decl": spec.authn_context_decl,
                "level": level,
                "authn_auth": authn_authority
            }
        else:
            raise NotImplementedError()

        m = hashlib.md5()
        for attr in ["method", "level", "authn_auth"]:
            m.update(str(_info[attr]))
        try:
            _txt = "%s" % _info["decl"]
        except KeyError:
            pass
        else:
            m.update(_txt)

        _ref = m.hexdigest()
        self.db["info"][_ref] = _info
        try:
            self.db["key"][key].append(_ref)
        except KeyError:
            self.db["key"][key] = [_ref]

    def remove(self, spec, method=None, level=0, authn_authority=""):
        if spec.authn_context_class_ref:
            _cls_ref = spec.authn_context_class_ref.text
            try:
                _refs = self.db["key"][_cls_ref]
            except KeyError:
                return
            else:
                _remain = []
                for _ref in _refs:
                    item = self.db["info"][_ref]
                    if method and method != item["method"]:
                        _remain.append(_ref)
                    if level and level != item["level"]:
                        _remain.append(_ref)
                    if authn_authority and \
                            authn_authority != item["authn_authority"]:
                        _remain.append(_ref)
                if _remain:
                    self.db[_cls_ref] = _remain

    def _pick_by_class_ref(self, cls_ref, comparision_type="exact"):
        func = getattr(self, comparision_type)
        try:
            _refs = self.db["key"][cls_ref]
        except KeyError:
            return []
        else:
            _item = self.db["info"][_refs[0]]
            _level = _item["level"]
            if _item["method"]:
                res = [(_item["method"], _refs[0])]
            else:
                res = []
            for ref in _refs[1:]:
                item = self.db[ref]
                res.append((item["method"], ref))
                if func(_level, item["level"]):
                    _level = item["level"]
            for ref, _dic in self.db["info"].items():
                if ref in _refs:
                    continue
                elif func(_level, _dic["level"]):
                    if _dic["method"]:
                        _val = (_dic["method"], ref)
                        if _val not in res:
                            res.append(_val)
            return res

    def pick(self, req_authn_context=None):
        """
        Given the authentication context find zero or more places where
        the user could be sent next. Ordered according to security level.

        :param req_authn_context: The requested context as an
            RequestedAuthnContext instance
        :return: An URL
        """

        if req_authn_context is None:
            return self._pick_by_class_ref(UNSPECIFIED, "minimum")
        if req_authn_context.authn_context_class_ref:
            if req_authn_context.comparison:
                _cmp = req_authn_context.comparison
            else:
                _cmp = "minimum"
            return self._pick_by_class_ref(
                req_authn_context.authn_context_class_ref.text, _cmp)
        elif req_authn_context.authn_context_decl_ref:
            if req_authn_context.comparison:
                _cmp = req_authn_context.comparison
            else:
                _cmp = "minimum"
            return self._pick_by_class_ref(
                req_authn_context.authn_context_decl_ref, _cmp)

    def match(self, requested, provided):
        if requested == provided:
            return True
        else:
            return False

    def __getitem__(self, ref):
        return self.db["info"][ref]


def authn_context_factory(text):
    # brute force
    for mod in [ippword, mobiletwofactor, ppt, pword, sslcert]:
        inst = mod.authentication_context_declaration_from_string(text)
        if inst:
            return inst

    return None


def authn_context_decl_from_extension_elements(extelems):
    res = extension_elements_to_elements(extelems, [ippword, mobiletwofactor,
                                                    ppt, pword, sslcert])
    try:
        return res[0]
    except IndexError:
        return None


def authn_context_class_ref(ref):
    return AuthnContext(authn_context_class_ref=AuthnContextClassRef(text=ref))


def requested_authn_context(class_ref, comparison="minimum"):
    return RequestedAuthnContext(
        authn_context_class_ref=AuthnContextClassRef(text=class_ref),
        comparison=comparison)