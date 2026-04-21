from django.core.mail.backends.smtp import EmailBackend

class CustomEmailBackend(EmailBackend):
    def open(self):
        """
        Override to remove keyfile/certfile parameters from the TLS connection.
        Ensures the standard SMTP backend works without SSL certificate files.
        """
        if self.connection:
            return False
        try:
            # Create connection without any additional kwargs
            self.connection = self.connection_class(self.host, self.port)
            
            if self.use_tls:
                self.connection.starttls()  # Removed keyfile/certfile parameters
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise