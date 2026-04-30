PRIVKEY=rainer.key
CERTIFICATE=rainer.crt
CERTIFICATE_PEM=rainer.pem
CERTIFICATE_EXPIRATION=365

.PHONY: ssl validate tar
ssl: $(CERTIFICATE).base64 $(PRIVKEY).base64 $(CERTIFICATE_PEM)

validate: $(CERTIFICATE) $(PRIVKEY)
	openssl pkey -in $(PRIVKEY) -pubout -out rainer_pub.pem
	openssl x509 -in $(CERTIFICATE) -pubkey -noout -out certificate_pub.pem
	diff rainer_pub.pem certificate_pub.pem

%.base64: %
	base64 $< > $@

$(CERTIFICATE_PEM): $(CERTIFICATE)
	openssl x509 -inform DER -in $< -outform PEM -out $@

$(CERTIFICATE): $(PRIVKEY)
	openssl req -new -x509 -nodes -days $(CERTIFICATE_EXPIRATION) -key $< -out $@ -outform DER

$(PRIVKEY):
	openssl ecparam -name prime256v1 -genkey -noout -out $@ -outform DER

tar: ../automatic_rainer.tar.gz

../automatic_rainer.tar.gz:
	tar -czvf ../automatic_rainer.tar.gz .

clean:
	$(RM) *.crt *.key *.pem *.base64
