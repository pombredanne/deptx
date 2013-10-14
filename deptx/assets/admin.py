from django.contrib import admin
from assets.models import Unit, Requisition, Task, Document, Mission, Case

class CaseDocumentInline(admin.StackedInline):
    model = Document
    extra = 0
 
class CaseAdmin(admin.ModelAdmin):
    inlines = [CaseDocumentInline]
    


admin.site.register(Unit)
admin.site.register(Requisition)
admin.site.register(Task)
admin.site.register(Document)
admin.site.register(Mission)
admin.site.register(Case, CaseAdmin)
#admin.site.register(Case,)


