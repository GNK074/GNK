from fastapi import APIRouter
from app.core.config import settings
router = APIRouter()
SERVICES = [
    ('Equity & Options Research','https://www.gnkalgo.com/services/equity-options-research/'),
    ('Commodity (MCX) Research','https://www.gnkalgo.com/services/commodity-research/'),
    ('API Trading Support','https://www.gnkalgo.com/services/api-trading-support/'),
    ('Premium RA + API Combo','https://www.gnkalgo.com/services/ra-api-support/'),
]
QUICK_LINKS = [(name, 'https://www.gnkalgo.com/'+slug+'/') for name,slug in [
    ('Terms and Conditions','terms'),('Disclosure','disclosure'),('Investor Charter','investor-charter'),
    ('Grievance Redressal Process','grievance-redressal'),('Refund Policy','refund'),('Complaint Status','complaint-status')]]
SOCIALS = [('Telegram','https://t.me/gnkalgo_research_official'),('Instagram','https://www.instagram.com/gnkalgo'),('Facebook','https://www.facebook.com/gnkalgoads/'),('LinkedIn','https://www.linkedin.com/company/gnkalgo-research/'),('X (Twitter)','https://x.com/gnkalgo')]

@router.get('/api/v1/public/contact')
def contact():
    registered = settings.company_registration_verified and bool(settings.company_legal_name and settings.company_sebi_registration)
    channels = settings.contact_channels_verified
    return {
        'company': {'name': settings.company_legal_name if registered else 'GnKAlgo', 'registration_verified': registered,
            'sebi_registration': settings.company_sebi_registration if registered else None,
            'basl_applicable': bool(registered and settings.company_basl_applicable),
            'basl_membership': settings.company_basl_membership if registered and settings.company_basl_applicable else None,
            'description': 'We are SEBI registered as Research Analyst. Providing research recommendations to traders and investors of Indian equity market.' if registered else 'GnKAlgo provides account, broker-integration and trading-platform technology. Contact us for platform and technical-support information.'},
        'channels_verified': channels,
        'phones': [{'label':'Level 1 Support','display':'+91 8297200073','href':'tel:+918297200073'}, {'label':'Level 2 Escalation','display':'+91 8297200074','href':'tel:+918297200074'}] if channels else [],
        'emails': ['info@gnkalgo.com','gnkalgo.admin@gmail.com'] if channels else [],
        'website':'https://gnkalgo.com/', 'office_hours':'9:00 AM – 6:00 PM IST',
        'location': settings.company_office_address if settings.company_office_address_verified else 'Bangalore – 560049',
        'maps_address': settings.company_office_address if settings.company_office_address_verified else None,
        'services':[{'label':name,'href':url} for name,url in SERVICES],
        'quick_links':[{'label':name,'href':url} for name,url in QUICK_LINKS],
        'socials':[{'label':name,'href':url} for name,url in SOCIALS] if channels else [],
        'security_policy': 'GnKAlgo Research exclusively communicates via verified channels listed on this domain. We never request direct fund transfers to personal accounts.' if channels else 'Use only contact channels published on this domain. We never request direct fund transfers to personal accounts.',
        'regulatory_notice': 'Registration granted by SEBI, membership of BASL and certification from NISM in no way guarantee performance of the intermediary or provide any assurance of returns to investors.' if registered and settings.company_basl_applicable else None,
        'disclaimer': 'Investments in securities market are subject to market risks. Read all related documents carefully before investing.',
    }
