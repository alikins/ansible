
# This is a dummy cacert provided for Mac OS since you need at least 1
# ca cert, regardless of validity, for Python on Mac OS to use the
# keychain functionality in OpenSSL for validating SSL certificates.
# See: http://mercurial.selenic.com/wiki/CACertificates#Mac_OS_X_10.6_and_higher
DUMMY_CA_CERT = """-----BEGIN CERTIFICATE-----
MIICvDCCAiWgAwIBAgIJAO8E12S7/qEpMA0GCSqGSIb3DQEBBQUAMEkxCzAJBgNV
BAYTAlVTMRcwFQYDVQQIEw5Ob3J0aCBDYXJvbGluYTEPMA0GA1UEBxMGRHVyaGFt
MRAwDgYDVQQKEwdBbnNpYmxlMB4XDTE0MDMxODIyMDAyMloXDTI0MDMxNTIyMDAy
MlowSTELMAkGA1UEBhMCVVMxFzAVBgNVBAgTDk5vcnRoIENhcm9saW5hMQ8wDQYD
VQQHEwZEdXJoYW0xEDAOBgNVBAoTB0Fuc2libGUwgZ8wDQYJKoZIhvcNAQEBBQAD
gY0AMIGJAoGBANtvpPq3IlNlRbCHhZAcP6WCzhc5RbsDqyh1zrkmLi0GwcQ3z/r9
gaWfQBYhHpobK2Tiq11TfraHeNB3/VfNImjZcGpN8Fl3MWwu7LfVkJy3gNNnxkA1
4Go0/LmIvRFHhbzgfuo9NFgjPmmab9eqXJceqZIlz2C8xA7EeG7ku0+vAgMBAAGj
gaswgagwHQYDVR0OBBYEFPnN1nPRqNDXGlCqCvdZchRNi/FaMHkGA1UdIwRyMHCA
FPnN1nPRqNDXGlCqCvdZchRNi/FaoU2kSzBJMQswCQYDVQQGEwJVUzEXMBUGA1UE
CBMOTm9ydGggQ2Fyb2xpbmExDzANBgNVBAcTBkR1cmhhbTEQMA4GA1UEChMHQW5z
aWJsZYIJAO8E12S7/qEpMAwGA1UdEwQFMAMBAf8wDQYJKoZIhvcNAQEFBQADgYEA
MUB80IR6knq9K/tY+hvPsZer6eFMzO3JGkRFBh2kn6JdMDnhYGX7AXVHGflrwNQH
qFy+aenWXsC0ZvrikFxbQnX8GVtDADtVznxOi7XzFw7JOxdsVrpXgSN0eh0aMzvV
zKPZsZ2miVGclicJHzm5q080b1p/sZtuKIEZk6vZqEg=
-----END CERTIFICATE-----
"""
