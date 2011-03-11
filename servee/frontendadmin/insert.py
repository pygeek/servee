from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.contrib.admin.util import unquote
from django.http import HttpResponse
from django.template import RequestContext
from django.template.loader import get_template
from django.shortcuts import render_to_response
from django.utils.functional import update_wrapper
from servee.utils import space_out_camel_case

class BaseInsert(object):
    """
    Insert classes are the things that go on the wysiwyg tools under 'Insert'.
    
    Some Examples might include (a few are in contrib):
    * Pictures
    * Video
    * Documents
    * YouTube Representations
    * Other Model Representations
    * oEmbed Links
    
    ModelInsert is what you should use if you are creating an Insert from a Django Model, otherwise use BaseInsert and extend from there.
    
    """
    def __init__(self, admin_site):
        self.admin_site = admin_site
    
    
    def base_url(self):
        """
        Should not be overwritten, also used as a slug
        """
        return self.__class__.__name__.lower()
    
    def nav_title(self):
        return space_out_camel_case(self.__class__.__name__)
    
    def title(self):
        return space_out_camel_case(self.__class__.__name__)
    
    def items(self):
        return NotImplementedError
    
    def get_items(self):
        return NotImplementedError
    
    def add_item(self):
        return NotImplementedError
    
    def edit_item(self, item):
        return NotImplementedError
    
    def content(self):
        return NotImplementedError
    
    def render_url(self):
        return NotImplementedError
    
    def get_urls():
        """
        get_urls() should return a set of patterns to be added to the /servee/ urls.
        """
        return []

class ModelInsert(BaseInsert):
    """
    Should only be subclassed, never just _used_, always set the model in the subclass

    Fair amounts of this have been cargo-culted from Django, Tests should be written,
    and any review/notes would be helpful.
    """
    ordering = None
    model = None
    
    def __init__(self, *args, **kwargs):
        """
        self.model should be set before calling super(<NewClass>, self).__init__...
        """
        self.item_panel_template = [
            "servee/wysiwyg/insert/%s/%s/_panel.html" % (self.model._meta.app_label, self.model._meta.module_name),
            "servee/wysiwyg/insert/%s/_panel.html" % (self.model._meta.app_label),            
            "servee/wysiwyg/insert/_panelt.html",
        ]
        self.item_display_template = [
            "servee/wysiwyg/insert/%s/%s/_list.html" % (self.model._meta.app_label, self.model._meta.module_name),
            "servee/wysiwyg/insert/%s/_list.html" % (self.model._meta.app_label),            
            "servee/wysiwyg/insert/_item_list.html",
        ]
        self.item_detail_template = [
            "servee/wysiwyg/insert/%s/%s/_detail.html" % (self.model._meta.app_label, self.model._meta.module_name),
            "servee/wysiwyg/insert/%s/_detail.html" % (self.model._meta.app_label),            
            "servee/wysiwyg/insert/_item_detail.html",
        ]
        self.item_list_template  = [
            "servee/wysiwyg/insert/%s/%s/_list.html" % (self.model._meta.app_label, self.model._meta.module_name),
            "servee/wysiwyg/insert/%s/_list.html" % (self.model._meta.app_label),            
            "servee/wysiwyg/insert/_item_list.html",
        ]
        self.item_render_template  = [
            "servee/wysiwyg/insert/%s/%s/_render.html" % (self.model._meta.app_label, self.model._meta.module_name),
            "servee/wysiwyg/insert/%s/_render.html" % (self.model._meta.app_label),            
            "servee/wysiwyg/insert/_item_render.html",
        ]
        super(ModelInsert, self).__init__(*args, **kwargs)
    
    def get_object(self, object_id):
        """
        Returns an instance matching the primary key provided. ``None``  is
        returned if no match is found (or the object_id failed validation
        against the primary key field).
        """
        model = self.model
        try:
            object_id = model._meta.pk.to_python(object_id)
            return self.queryset().get(pk=object_id)
        except (model.DoesNotExist, ValidationError):
            return None
    
    def queryset(self, ordering=None):
        qs = self.model._default_manager.get_query_set()
        if not ordering:
            ordering = self.ordering or () # otherwise we might try to *None, which is bad ;)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
    
    def items(self):
        return self.queryset()
    
    def render(self, item):
        """
        Gets an item pk, and renders it to HTML string to be insert.
        item is passed to the template (item_render_template) with context
        item,
        MEDIA_URL,
        STATIC_URL
        """
        item = self.model._default_manager.get(pk=item)
        t = get_template(self.item_render_template)
        return t.render({
            "MEDIA_URL": settings.MEDIA_URL,
            "STATIC_URL": settings.STATIC_URL,
            "item": item,
        })
    
    def get_items(self):
        """
        Ideally, this will be a method that will also sort, for pagination, or filtering
        """
        return self.items()
    
    def nav_title(self):
        return self.model._meta.module_name.title()
    
    def get_urls(self):
        """
        Returns urls to get the panel, get/filter list, add/upload, delete and get rendered output.
        """
        from django.conf.urls.defaults import patterns, url
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)
        
        info = (self.model._meta.app_label, self.model._meta.module_name)
        
        return patterns("",
            url(r"^panel/$",
                wrap(self.panel_view),
                name="%s_%s_panel" % info),
            url(r"^list/$",
                wrap(self.list_view),
                name="%s_%s_list" % info),
            #url(r"^add_minimal/$",
            #    wrap(self.add_view),
            #    name="%s_%s_add" % info),
            url(r"^(.+)/detail/$",
                wrap(self.detail_view),
                name="%s_%s_detail" % info),
            url(r"^(.+)/render/$",
                wrap(self.render_view),
                name="%s_%s_render" % info),
            url(r"^(.+)/delete/$",
                wrap(self.delete_view),
                name="%s_%s_delete" % info),
        )
    
    @property
    def urls(self):
        return self.get_urls()
    
    def panel_view(self, request):
        return render_to_response(self.item_panel_template, {"insert": self},
            context_instance=RequestContext(request))

    def list_url(self):
        return reverse("%s:%s_%s_list" % (
            self.admin_site.name,
            self.model._meta.app_label,
            self.model._meta.module_name
        ))
                
    def list_view(self, request):
        return render_to_response(self.item_list_template, {"insert": self},
            context_instance=RequestContext(request))
    
    def detail_view(self, request, object_id):
        obj = self.get_object(unquote(object_id))
        
        return render_to_response(self.item_detail_template, {"insert": self, "object": obj},
            context_instance=RequestContext(request))
    
    def render_url(self, object_id):
        return reverse("%s:%s_%s_render" % (
            self.admin_site.name,
            self.model._meta.app_label,
            self.model._meta.module_name
        ), args=(object_id,))
        
    def render_view(self, request, object_id):
        obj = self.get_object(unquote(object_id))
        
        return render_to_response(self.item_render_template, {"insert": self, "object": obj},
            context_instance=RequestContext(request))
    
    def delete_view(self, request, object_id):
        """
        This view isn't really safe to cross-site attacks, some sort of post confirmation with CSRF would be better.
        """
        obj = self.get_object(unquote(object_id))
        obj.delete()
        return HttpResponse("Deleted")
