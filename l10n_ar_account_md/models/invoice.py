# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning
import openerp.addons.decimal_precision as dp
import re
import logging
_logger = logging.getLogger(__name__)


class account_invoice(models.Model):
    _inherit = "account.invoice"

    currency_rate = fields.Float(
        string='Currency Rate',
        copy=False,
        digits=(16, 4),
        # TODO make it editable, we hace to change move create method
        readonly=True,
        )
    invoice_number = fields.Integer(
        compute='_get_invoice_number',
        string=_("Invoice Number"),
        )
    point_of_sale = fields.Integer(
        compute='_get_invoice_number',
        string=_("Point Of Sale"),
        )
    printed_amount_tax = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('Tax')
        )
    printed_amount_untaxed = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('Subtotal')
        )
    # no gravado en iva
    vat_untaxed = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('VAT Untaxed')
        )
    # exento en iva
    vat_exempt_amount = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('VAT Exempt Amount')
        )
    # von iva
    vat_amount = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('VAT Amount')
        )
    # von iva
    vat_base_amount = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('VAT Base Amount')
        )
    other_taxes_amount = fields.Float(
        compute="_get_taxes_and_prices",
        digits=dp.get_precision('Account'),
        string=_('Other Taxes Amount')
        )
    printed_tax_ids = fields.One2many(
        compute="_get_taxes_and_prices",
        comodel_name='account.invoice.tax',
        string=_('Tax')
        )
    vat_tax_ids = fields.One2many(
        compute="_get_taxes_and_prices",
        comodel_name='account.invoice.tax',
        string=_('VAT Taxes')
        )
    not_vat_tax_ids = fields.One2many(
        compute="_get_taxes_and_prices",
        comodel_name='account.invoice.tax',
        string=_('Not VAT Taxes')
        )
    vat_discriminated = fields.Boolean(
        _('Discriminate VAT?'),
        compute="get_vat_discriminated",
        help=_("Discriminate VAT on Invoices?"),
        )
    available_journal_document_class_ids = fields.Many2many(
        'account.journal.afip_document_class',
        compute='_get_available_journal_document_class',
        string=_('Available Journal Document Classes'),
        )
    supplier_invoice_number = fields.Char(
        copy=False,
        )
    journal_document_class_id = fields.Many2one(
        'account.journal.afip_document_class',
        'Document Type',
        readonly=True,
        ondelete='restrict',
        states={'draft': [('readonly', False)]}
        )
    afip_incoterm_id = fields.Many2one(
        'afip.incoterm',
        'Incoterm',
        readonly=True,
        states={'draft': [('readonly', False)]}
        )
    afip_document_class_id = fields.Many2one(
        'afip.document_class',
        related='journal_document_class_id.afip_document_class_id',
        string='Document Type',
        copy=False,
        readonly=True,
        store=True,
        )
    afip_document_number = fields.Char(
        string='Document Number',
        copy=False,
        readonly=True,
        )
    responsability_id = fields.Many2one(
        'afip.responsability',
        string='Responsability',
        readonly=True,
        copy=False,
        )
    formated_vat = fields.Char(
        string='Responsability',
        related='commercial_partner_id.formated_vat',
        )
    document_number = fields.Char(
        compute='_get_document_number',
        # string=_('Document Number'),
        # waiting for a PR 9081 to fix computed fields translations
        string='Número de documento',
        readonly=True,
        )
    next_invoice_number = fields.Integer(
        related='journal_document_class_id.sequence_id.number_next_actual',
        string='Next Document Number',
        readonly=True
        )
    use_documents = fields.Boolean(
        related='journal_id.use_documents',
        string='Use Documents?',
        readonly=True
        )
    use_argentinian_localization = fields.Boolean(
        related='company_id.use_argentinian_localization',
        string='Use Argentinian Localization?',
        readonly=True,
        )
    point_of_sale_type = fields.Selection(
        related='journal_id.point_of_sale_id.type',
        readonly=True,
        )
    # estos campos los agregamos en este modulo pero en realidad los usa FE
    # pero entendemos que podrian ser necesarios para otros tipos, por ahora
    # solo lo vamos a hacer requerido si el punto de venta es del tipo
    # electronico
    afip_concept = fields.Selection(
        compute='_get_concept',
        # store=True,
        selection=[('1', 'Producto / Exportación definitiva de bienes'),
                   ('2', 'Servicios'),
                   ('3', 'Productos y Servicios'),
                   ('4', '4-Otros (exportación)'),
                   ],
        string="AFIP concept",
        )
    afip_service_start = fields.Date(
        string='Service Start Date'
        )
    afip_service_end = fields.Date(
        string='Service End Date'
        )

    @api.one
    @api.depends(
        'invoice_line',
        'invoice_line.product_id',
        'invoice_line.product_id.type',
        'use_argentinian_localization',
    )
    def _get_concept(self):
        afip_concept = False
        if self.point_of_sale_type in ['online', 'electronic']:
            # exportaciones
            product_types = set(
                [x.product_id.type for x in self.invoice_line if x.product_id])
            consumible = set(['consu', 'product'])
            service = set(['service'])
            mixed = set(['consu', 'service', 'product'])
            # default value "product"
            afip_concept = '1'
            if product_types.issubset(mixed):
                afip_concept = '3'
            if product_types.issubset(service):
                afip_concept = '2'
            if product_types.issubset(consumible):
                afip_concept = '1'
            if self.afip_document_class_id.afip_code in [19, 20, 21]:
                # TODO verificar esto, como par expo no existe 3 y existe 4
                # (otros), considermaos que un mixto seria el otros
                if afip_concept == '3':
                    afip_concept = '4'
        self.afip_concept = afip_concept

    @api.one
    def _get_taxes_and_prices(self):
        """
        """

        vat_taxes = self.tax_line.filtered(
            lambda r: (
                r.tax_code_id.type == 'tax' and r.tax_code_id.tax == 'vat'))
        vat_amount = sum(
            vat_taxes.mapped('amount'))
        vat_base_amount = sum(
            vat_taxes.mapped('base'))

        not_vat_taxes = self.tax_line - vat_taxes

        other_taxes_amount = sum(
            (self.tax_line - vat_taxes).mapped('amount'))

        vat_exempt_amount = sum(vat_taxes.filtered(
                lambda r: r.tax_code_id.afip_code == 2).mapped('base'))

        vat_untaxed = sum(vat_taxes.filtered(
                lambda r: r.tax_code_id.afip_code == 1).mapped('base'))

        if self.vat_discriminated:
            printed_amount_untaxed = self.amount_untaxed
            printed_taxes = self.tax_line
        else:
            printed_amount_untaxed = self.amount_total
            printed_taxes = False

        self.printed_amount_untaxed = printed_amount_untaxed
        self.printed_tax_ids = printed_taxes
        self.printed_amount_tax = self.amount_total - printed_amount_untaxed
        self.vat_tax_ids = vat_taxes
        self.not_vat_tax_ids = not_vat_taxes
        self.vat_amount = vat_amount
        self.other_taxes_amount = other_taxes_amount
        self.vat_exempt_amount = vat_exempt_amount
        self.vat_untaxed = vat_untaxed
        self.vat_base_amount = vat_base_amount

    @api.multi
    def name_get(self):
        TYPES = {
            'out_invoice': _('Invoice'),
            'in_invoice': _('Supplier Invoice'),
            'out_refund': _('Refund'),
            'in_refund': _('Supplier Refund'),
        }
        result = []
        for inv in self:
            result.append((
                inv.id,
                "%s %s" % (
                    inv.document_number or TYPES[inv.type],
                    inv.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(
                [('document_number', '=', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.one
    @api.depends(
        'journal_document_class_id',
        'company_id',
        )
    def get_vat_discriminated(self):
        vat_discriminated = False
        if self.afip_document_class_id.document_letter_id.vat_discriminated or self.company_id.invoice_vat_discrimination_default == 'discriminate_default':
            vat_discriminated = True
        self.vat_discriminated = vat_discriminated

    @api.one
    @api.depends('afip_document_number', 'number')
    def _get_invoice_number(self):
        """ Funcion que calcula numero de punto de venta y numero de factura
        a partir del document number. Es utilizado principalmente por el modulo
        de vat ledger citi
        """
        # TODO mejorar estp y almacenar punto de venta y numero de factura por separado
        # de hecho con esto hacer mas facil la carga de los comprobantes de compra
        str_number = self.afip_document_number or self.number or False
        if str_number and self.state not in ['draft', 'proforma', 'proforma2', 'cancel']:
            if self.afip_document_class_id.afip_code in [33, 99, 331, 332]:
                point_of_sale = '0'
                # leave only numbers and convert to integer
                invoice_number = str_number
            # despachos de importacion
            elif self.afip_document_class_id.afip_code == 66:
                point_of_sale = '0'
                invoice_number = '0'
            elif "-" in str_number:
                splited_number = str_number.split('-')
                invoice_number = splited_number.pop()
                point_of_sale = splited_number.pop()
            elif "-" not in str_number and len(str_number) == 12:
                point_of_sale = str_number[:4]
                invoice_number = str_number[-8:]
            else:
                raise Warning(_(
                    'Could not get invoice number and point of sale for invoice id %i') % (
                        self.id))
            self.invoice_number = int(re.sub("[^0-9]", "", invoice_number))
            self.point_of_sale = int(re.sub("[^0-9]", "", point_of_sale))

    _sql_constraints = [
        ('number_supplier_invoice_number',
            'unique(supplier_invoice_number, type, partner_id, company_id)',
         'Supplier Invoice Number must be unique per Supplier and Company!'),
    ]

    @api.one
    @api.depends('journal_id', 'partner_id')
    def _get_available_journal_document_class(self):
        invoice_type = self.type
        document_class_ids = []
        document_class_id = False

        # Lo hicimos asi porque si no podria dar errores si en el context habia
        # un default de otra clase
        self.available_journal_document_class_ids = self.env[
            'account.journal.afip_document_class']
        if invoice_type in [
                'out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            operation_type = self.get_operation_type(invoice_type)

            if self.use_documents:
                # corremos con sudo porque da errores con usuario portal en algunos casos
                letter_ids = self.sudo().get_valid_document_letters(
                    self.partner_id.id, operation_type, self.company_id.id)

                domain = [
                    ('journal_id', '=', self.journal_id.id),
                    ('afip_document_class_id.document_letter_id',
                        'in', letter_ids),
                    ]

                # If document_type in context we try to serch specific document
                document_type = self._context.get('document_type', False)
                if document_type:
                    document_classes = self.env[
                        'account.journal.afip_document_class'].search(
                        domain + [
                            ('afip_document_class_id.document_type',
                                '=', document_type)])
                    if document_classes.ids:
                        document_class_id = document_classes.ids[0]

                # For domain, we search all documents
                document_classes = self.env[
                    'account.journal.afip_document_class'].search(domain)
                document_class_ids = document_classes.ids

                # If not specific document type found, we choose another one
                if not document_class_id and document_class_ids:
                    document_class_id = document_class_ids[0]

        if invoice_type == 'in_invoice':
            other_afip_document_classes = (
                self.commercial_partner_id.other_afip_document_class_ids)

            domain = [
                ('journal_id', '=', self.journal_id.id),
                ('afip_document_class_id',
                    'in', other_afip_document_classes.ids),
                ]
            other_document_classes = self.env[
                'account.journal.afip_document_class'].search(domain)

            document_class_ids += other_document_classes.ids
            if other_document_classes:
                document_class_id = other_document_classes[0].id

        self.available_journal_document_class_ids = document_class_ids
        self.journal_document_class_id = document_class_id

    @api.one
    @api.constrains(
        'journal_id', 'partner_id',
        'journal_document_class_id',
        )
    def _get_document_class(self):
        """ Como los campos responsability y journal document class no los
        queremos hacer funcion porque no queremos que sus valores cambien nunca
        y como con la funcion anterior solo se almacenan solo si se crea desde
        interfaz, hacemos este hack de constraint para computarlos si no estan
        computados"""
        if not self.journal_document_class_id and self.available_journal_document_class_ids:
            self.journal_document_class_id = self.available_journal_document_class_ids[0]

    @api.one
    @api.depends('afip_document_number', 'number')
    def _get_document_number(self):
        if self.afip_document_number and self.afip_document_class_id:
            document_number = (
                self.afip_document_class_id.doc_code_prefix or '') + self.afip_document_number
        else:
            document_number = self.number
        self.document_number = document_number

    @api.one
    @api.constrains('supplier_invoice_number', 'partner_id', 'company_id')
    def _check_reference(self):
        if self.type in ['out_invoice', 'out_refund'] and self.reference and self.state == 'open':
            domain = [('type', 'in', ('out_invoice', 'out_refund')),
                      # ('reference', '=', self.reference),
                      ('document_number', '=', self.document_number),
                      ('journal_document_class_id.afip_document_class_id', '=',
                       self.journal_document_class_id.afip_document_class_id.id),
                      ('company_id', '=', self.company_id.id),
                      ('id', '!=', self.id)]
            invoice_ids = self.search(domain)
            if invoice_ids:
                raise Warning(_(
                    'Supplier Invoice Number must be unique per Supplier'
                    ' and Company!'))

    @api.multi
    def check_use_documents(self):
        # check invoices has document class but journal require it (we check
        # all invoices, not only argentinian ones)
        without_doucument_class = self.filtered(
            lambda r: (
                not r.afip_document_class_id and r.journal_id.use_documents))
        if without_doucument_class:
            raise Warning(_(
                'Some invoices have a journal that require a document but not '
                'document type has been selected.\n'
                'Invoices ids: %s' % without_doucument_class.ids))

    @api.multi
    def check_argentinian_invoice_taxes(self):
        """
        We make theis function to be used as a constraint but also to be called
        from other models like vat citi
        """
        # only check for argentinian localization companies
        _logger.info('Running checks related to argentinian documents')

        # we consider argentinian invoices the ones from companies with
        # use_argentinian_localization and that belongs to a journal with
        # use_documents
        argentinian_invoices = self.filtered(
            lambda r: (
                r.use_argentinian_localization and r.use_documents))
        if not argentinian_invoices:
            return True

        # check invoice tax has code
        without_tax_code = self.env['account.invoice.tax'].search([
            ('invoice_id', 'in', argentinian_invoices.ids),
            ('tax_code_id', '=', False),
            ])
        if without_tax_code:
            raise Warning(_(
                "You are using argentinian localization and there are some "
                "invoices with taxes that don't have tax code, tax code is "
                "required to generate this report. Invoies ids: %s" % (
                    without_tax_code.mapped('invoice_id.id'))))

        # check codes has argentinian tax attributes configured
        tax_codes = argentinian_invoices.mapped('tax_line.tax_code_id')
        unconfigured_tax_codes = tax_codes.filtered(
            lambda r: not r.type or not r.tax or not r.application)
        if unconfigured_tax_codes:
            raise Warning(_(
                "You are using argentinian localization and there are some tax"
                " codes that are not configured. Tax codes ids: %s" % (
                    unconfigured_tax_codes.ids)))

        # Check invoice with amount
        invoices_without_amount = self.search([
            ('id', 'in', argentinian_invoices.ids),
            ('amount_total', '=', 0.0)])
        if invoices_without_amount:
            raise Warning(_('Invoices ids %s amount is cero!') % (
                invoices_without_amount.ids))

        # Check invoice requiring vat

        # out invoice must have vat if are argentinian and from a company with
        # responsability that requires vat
        sale_invoices_with_vat = self.search([(
            'id', 'in', argentinian_invoices.ids),
            ('type', 'in', ['out_invoice', 'out_refund']),
            ('company_id.partner_id.responsability_id.vat_tax_required_on_sales_invoices',
                '=', True)])

        # check purchase invoice has supplier invoice number
        purchase_invoices = argentinian_invoices.filtered(
            lambda r: r.type in ('in_invoice', 'in_refund'))
        purchase_invoices_without_sup_number = purchase_invoices.filtered(
            lambda r: (not r.supplier_invoice_number))
        if purchase_invoices_without_sup_number:
            raise Warning(_(
                "Some purchase invoices don't have supplier nunmber.\n"
                "Invoices ids: %s" % purchase_invoices_without_sup_number.ids))

        # purchase invoice must have vat if document class letter has vat
        # discriminated
        purchase_invoices_with_vat = purchase_invoices.filtered(
            lambda r: (
                r.afip_document_class_id.document_letter_id.vat_discriminated))

        invoices_with_vat = (
            sale_invoices_with_vat + purchase_invoices_with_vat)

        for invoice in invoices_with_vat:
            # we check vat base amount is equal to amount untaxed
            # usamos una precision de 0.1 porque en algunos casos no pudimos
            # arreglar pbñe,as de redondedo 
            if abs(invoice.vat_base_amount - invoice.amount_untaxed) > 0.1:
                raise Warning(_(
                    "Invoice ID: %i\n"
                    "Invoice subtotal (%.2f) is different from invoice base"
                    " vat amount (%.2f)" % (
                        invoice.id,
                        invoice.amount_untaxed,
                        invoice.vat_base_amount)))

        # check purchase invoices that can't have vat. We check only the ones
        # with document letter because other documents may have or not vat tax
        purchase_invoices_without = purchase_invoices.filtered(
            lambda r: (
                r.afip_document_class_id.document_letter_id and
                not r.afip_document_class_id.document_letter_id.vat_discriminated))
        for invoice in purchase_invoices_without:
            if invoice.vat_tax_ids:
                raise Warning(_(
                    "Invoice ID %i shouldn't have any vat tax" % invoice.id))

        # Check except vat invoice
        afip_exempt_codes = ['Z', 'X', 'E', 'N', 'C']
        for invoice in argentinian_invoices:
            special_vat_taxes = invoice.tax_line.filtered(
                lambda r: r.tax_code_id.afip_code in [1, 2, 3])
            if (
                        special_vat_taxes
                        and invoice.fiscal_position.afip_code
                        not in afip_exempt_codes):
                raise Warning(_(
                    "If there you have choose a tax with 0, exempt or untaxed,"
                    " you must choose a fiscal position with afip code in %s. "
                    "Invoice id %i" % (
                        afip_exempt_codes, invoice.id)))

    @api.multi
    def action_move_create(self):
        """
        We add currency rate on move creation so it can be used by electronic
        invoice later on action_number
        """
        self.check_use_documents()
        self.check_argentinian_invoice_taxes()
        for inv in self:
            inv.currency_rate = inv.currency_id.compute(
                    1., inv.company_id.currency_id)
        return super(account_invoice, self).action_move_create()

    @api.multi
    def action_number(self):
        """
        A partir de este metodo no debería haber errores porque el modulo de
        factura electronica ya habria pedido el cae. Lo ideal sería hacer todo
        esto antes que se pida el cae pero tampoco se pueden volver a atras los
        conusmos de secuencias. TODO mejorar esa parte
        """
        obj_sequence = self.env['ir.sequence']

        # We write document_number field with next invoice number by
        # document type
        for obj_inv in self:
            _logger.info('Setting argentinian invoice and move data')
            invtype = obj_inv.type
            # if we have a journal_document_class_id is beacuse we are in a
            # company that use this function
            # also if it has a reference number we use it (for example when
            # cancelling for modification)
            inv_vals = {
                'responsability_id': self.partner_id.commercial_partner_id.responsability_id.id,
                # 'currency_rate': obj_inv.company_id.currency_id.compute(
                    # 1., obj_inv.currency_id)
                }
            if obj_inv.journal_document_class_id:
                if not obj_inv.afip_document_number:
                    if invtype in ('out_invoice', 'out_refund'):
                        if not obj_inv.journal_document_class_id.sequence_id:
                            raise Warning(_('Error!. Please define sequence on the journal related documents to this invoice.'))
                        afip_document_number = obj_sequence.next_by_id(
                            obj_inv.journal_document_class_id.sequence_id.id)
                    elif invtype in ('in_invoice', 'in_refund'):
                        afip_document_number = obj_inv.supplier_invoice_number
                    inv_vals['afip_document_number'] = afip_document_number
                # caso factura cancelada y veulta a validar, tiene
                # el document number seteado
                else:
                    afip_document_number = obj_inv.afip_document_number
                document_class_id = obj_inv.journal_document_class_id.afip_document_class_id.id
                obj_inv.move_id.write({
                    'document_class_id': document_class_id,
                    'afip_document_number': afip_document_number,
                    })
            obj_inv.write(inv_vals)
        res = super(account_invoice, self).action_number()
        return res

    @api.model
    def get_operation_type(self, invoice_type):
        if invoice_type in ['in_invoice', 'in_refund']:
            operation_type = 'purchase'
        elif invoice_type in ['out_invoice', 'out_refund']:
            operation_type = 'sale'
        else:
            operation_type = False
        return operation_type

    def get_valid_document_letters(
            self, cr, uid, partner_id, operation_type='sale',
            company_id=False, context=None):
        if context is None:
            context = {}

        document_letter_obj = self.pool.get('afip.document_letter')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        partner = self.pool.get('res.partner').browse(
            cr, uid, partner_id, context=context)

        if not partner_id or not company_id or not operation_type:
            return []

        partner = partner.commercial_partner_id

        if not company_id:
            company_id = context.get('company_id', user.company_id.id)
        company = self.pool.get('res.company').browse(
            cr, uid, company_id, context)

        if operation_type == 'sale':
            issuer_responsability_id = company.partner_id.responsability_id.id
            receptor_responsability_id = partner.responsability_id.id
        elif operation_type == 'purchase':
            issuer_responsability_id = partner.responsability_id.id
            receptor_responsability_id = company.partner_id.responsability_id.id
        else:
            raise except_orm(_('Operation Type Error'),
                             _('Operation Type Must be "Sale" or "Purchase"'))

        if not company.partner_id.responsability_id.id:
            raise except_orm(_('Your company has not setted any responsability'),
                             _('Please, set your company responsability in the company partner before continue.'))

        document_letter_ids = document_letter_obj.search(cr, uid, [(
            'issuer_ids', '=', issuer_responsability_id),
            ('receptor_ids', '=', receptor_responsability_id)],
            context=context)
        return document_letter_ids

    @api.multi
    def action_invoice_sent(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        assert len(
            self) == 1, 'This option should only be used for a single id at a time.'
        template = self.env.ref(
            'l10n_ar_invoice.email_template_edi_invoice', False)
        compose_form = self.env.ref(
            'mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='account.invoice',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }
