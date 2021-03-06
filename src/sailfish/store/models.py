'''
Created on Aug 29, 2009

@author: Nick
'''
from google.appengine.ext import db
from google.appengine.ext.db import djangoforms
from auth.models import UserProfile
import logging
import settings
import urllib2
from sailfish.utils import send_templated_email

class Product(db.Model):
    """
    Represents a product in the catalog.
    """
    name = db.StringProperty()
    description = db.TextProperty()
    short_description = db.TextProperty()
    price = db.FloatProperty(indexed=False)
    icon = db.StringProperty(indexed=False)
    download_url = db.StringProperty(indexed=False)
    download_url_ota = db.StringProperty(indexed=False)
    # Secret used for activation
    secret = db.StringProperty(indexed=False)
    # if this is False product will only be shown for Admin
    available = db.BooleanProperty(indexed=False)
    # url of associated site
    service_url = db.StringProperty(indexed=False)
    
    def is_freeware(self):
        return self.price == 0
        
class ProductForm(djangoforms.ModelForm):
    class Meta:
        model = Product
        
class UserProduct(db.Model):
    """
    Represent's a user's product.  Parent entity = UserProfile.
    """
    product = db.Reference(Product)
    pin = db.StringProperty()
    purchase_date = db.DateTimeProperty()        
    
    @classmethod
    def create_from_tx(cls, tx):
        """
        Initialize with given transaction, and save the product to the 
        database.
        """
        up = UserProduct(parent=tx.user())
        up.product = db.Key(tx.product_key)
        up.purchase_date = tx.txdate
        up.pin = tx.pin
        up.put()        
        uk = UserKey(parent=tx.user())
        uk.product = db.Key(tx.product_key)
        uk.pin = tx.pin
        uk.put()
        return up
        
    def user(self):
        return self.parent()
        
    def send_thankyou_mail(self):
        """
        Called after IPN.  Send a confirmation to the user.
        """
        send_templated_email("Your Sailfish Mobile purchase confirmation", 
                                   "store/thankyou_mail.txt", 
                                   { 'userproduct': self,
                                     'tx': self.parent() },
                                    self.parent().preferred_email or self.parent().emails[0])
        
    def get_activation_code(self):
        """
        Activation code based on user id and app's secret
        """
        s = self.pin + "|" + self.product.secret
        import md5
        import base64
        return base64.encodestring(md5.md5(s).digest()).strip()
    
    def validate_code(self, code):
        """
        Return true if code is valid.
        """
        return self.get_activation_code() == code
    
    @classmethod
    def get_product(cls, user, product):
        """
        If the specified user already has a record for the product,
        returns the userproduct record.
        Otherwise, return None.
        """
        q = UserProduct.all()
        q.ancestor(user)
        q.filter("product = ", product)
        return q.get()
    
class UserKey(db.Model):
    '''
    Represents a single installation of the product.
    Parent entity = userprofile.
    Used for sync.
    '''
    product = db.Reference(Product)
    pin = db.StringProperty()
        
    def user(self):
        return self.parent()
    
        
class PaypalRequest(db.Model):
    """
    Stores a paypal request awaiting confirmation.
    Parent entity = user.
    """
    # Product is stored only as the key, rather than a reference, so that it
    # may be read in a transaction.
    product_key = db.StringProperty()
    txdate = db.DateTimeProperty(auto_now_add=True)
    txnid = db.StringProperty()
    amount = db.FloatProperty()
    pin = db.StringProperty()
    status = db.StringProperty()
    
    def user(self):
        return self.parent()
    
    def process_ipn(self, request):
        """
        Process the given IPN request (must have been already validated)
        This should be run within a transaction.
        """
        if self.status != "COMPLETE" and \
            request.POST["payment_status"] == "Completed" and \
            request.POST["mc_gross"] == str(self.amount) and \
            request.POST["mc_currency"] == "USD":
            userprod = UserProduct.create_from_tx(self)            
            self.status = "COMPLETE"
            self.txnid = request.POST["txn_id"]
            self.put()
            logging.info("Completed transaction with paypal id " + self.txnid)
            return userprod
        logging.warn("Invalid transaction... " + 
                     "status = " + self.status + "...  " + 
                     "Amt = " + str(self.amount) + "...  " + 
                     "Pmt Status = " + request.POST["payment_status"] + "... " + 
                     "Txn ID = " + request.POST["txn_id"])
        return None
            
    
    @classmethod
    def prepare(cls, product, user, pin):
        """
        Save and return request to the database with current user and 
        designated product.
        """
        tx = PaypalRequest(parent=user)
        tx.product_key = str(product.key())
        tx.amount = product.price
        tx.pin = pin.upper()
        tx.status = "PENDING"
        tx.put()
        return tx
    
    @classmethod
    def validate_ipn(cls, request):
        """
        Validate the given request with Paypal.
        Return true if valid.
        """
        if settings.DEBUG:
            base_url = "https://www.sandbox.paypal.com/cgi-bin/webscr"
        else:
            base_url = "https://www.paypal.com/cgi-bin/webscr"
        data = "cmd=_notify-validate&" + request.raw_post_data
        response = urllib2.urlopen(base_url, data)
        response_data = response.read()
        if response_data == "VERIFIED":
            logging.info("Received paypal notification: " + request.POST["txn_id"])
            return True
        else:
            logging.warn("Invalid IPN data: " + 
                         "Post = [" + request.raw_post_data + "]; " + 
                         "Response = [" + response_data + "]")
            return False
        
        