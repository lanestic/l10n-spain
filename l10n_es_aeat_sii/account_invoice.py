# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import openerp.exceptions
from openerp.osv import fields, osv, orm
from requests import Session
from zeep import Client
from zeep.transports import Transport
from zeep.plugins import HistoryPlugin
from datetime import datetime

class account_invoice(osv.Model):
    _inherit = 'account.invoice'

    _columns = {
        'sii_sent': fields.boolean('SII Sent'),
        'sii_return': fields.text('SII Return')
    }     

    def _change_date_format(self, cr, uid, date):
        datetimeobject = datetime.strptime(date,'%Y-%m-%d')
        new_date = datetimeobject.strftime('%d-%m-%Y')
        return new_date
    
    
    def _get_header(self, cr, uid, ids, company, TipoComunicacion):
        header = { "IDVersionSii": company.version_sii,
                   "Titular": {
                      "NombreRazon": company.name,
                      "NIF": company.vat[2:]},
                   "TipoComunicacion": TipoComunicacion 
        }
        return header
    
    
    def _get_tax_line_req(self, cr, uid, tax_type, line, line_taxes):
        taxes = False
        if len(line_taxes) > 1:
            req_ids = self.pool.get('account.tax').search(cr, uid, [('name', 'in', [
                'P_REQ5.2', 'S_REQ5.2', 'P_REQ1.4', 'S_REQ1.4', 'P_REQ0.5',
                'S_REQ0.5'])])
            for tax in line_taxes:
                if tax.id in req_ids:
                    price = line.price_unit * (1 - (
                        line.discount or 0.0) / 100.0)
                    taxes = self.pool.get('account.tax').compute_all(cr, uid, [tax], price, line.quantity, line.product_id, line.invoice_id.partner_id)
                    taxes['percetage'] = tax.amount
                    return taxes
        return taxes
    
    
    def _get_sii_tax_line(self, cr, uid, tax_line, line, line_taxes):
        tax_type = tax_line.amount * 100
        tax_line_req = self._get_tax_line_req(cr, uid, tax_type, line, line_taxes)
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxes = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        if tax_line_req:
            TipoRecargo = tax_line_req['percetage'] * 100
            CuotaRecargo = tax_line_req['taxes'][0]['amount']
        else:
            TipoRecargo = 0
            CuotaRecargo = 0
        tax_sii = {
            "TipoImpositivo":tax_type,
            "BaseImponible":taxes['total'],
            "CuotaRepercutida":taxes['taxes'][0]['amount'],
            "TipoRecargoEquivalencia":TipoRecargo,
            "CuotaRecargoEquivalencia":CuotaRecargo
        }
        return tax_sii
    
    
    def _update_sii_tax_line(self, cr, uid, taxes, tax_line, line, line_taxes):
        tax_type = tax_type = tax_line.amount * 100
        tax_line_req = self._get_tax_line_req(cr, uid, tax_type, line, line_taxes)
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxesc = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        if tax_line_req:
            TipoRecargo = tax_line_req['percetage'] * 100
            CuotaRecargo = tax_line_req['taxes'][0]['amount']
        else:
            TipoRecargo = 0
            CuotaRecargo = 0
        taxes[str(tax_type)]['BaseImponible'] += taxesc['total']
        taxes[str(tax_type)]['CuotaRepercutida'] += taxesc['taxes'][0]['amount']
        taxes[str(tax_type)]['TipoRecargoEquivalencia'] = TipoRecargo
        taxes[str(tax_type)]['CuotaRecargoEquivalencia'] += CuotaRecargo
        return taxes

    def _get_sii_tax_linep(self, cr, uid, tax_line, line, line_taxes):
        tax_type = tax_line.amount * 100
        tax_line_req = self._get_tax_line_req(cr, uid, tax_type, line, line_taxes)
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxes = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        if tax_line_req:
            TipoRecargo = tax_line_req['percetage'] * 100
            CuotaRecargo = tax_line_req['taxes'][0]['amount']
        else:
            TipoRecargo = 0
            CuotaRecargo = 0
        tax_sii = {
            "TipoImpositivo":tax_type,
            "BaseImponible":taxes['total'],
            "CuotaSoportada":taxes['taxes'][0]['amount'],
            "TipoRecargoEquivalencia":TipoRecargo,
            "CuotaRecargoEquivalencia":CuotaRecargo
        }
        return tax_sii


    def _update_sii_tax_linep(self, cr, uid, taxes, tax_line, line, line_taxes):
        tax_type = tax_type = tax_line.amount * 100
        tax_line_req = self._get_tax_line_req(cr, uid, tax_type, line, line_taxes)
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxesc = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        if tax_line_req:
            TipoRecargo = tax_line_req['percetage'] * 100
            CuotaRecargo = tax_line_req['taxes'][0]['amount']
        else:
            TipoRecargo = 0
            CuotaRecargo = 0
        taxes[str(tax_type)]['BaseImponible'] += taxesc['total']
        taxes[str(tax_type)]['CuotaSoportada'] += taxesc['taxes'][0]['amount']
        taxes[str(tax_type)]['TipoRecargoEquivalencia'] = TipoRecargo
        taxes[str(tax_type)]['CuotaRecargoEquivalencia'] += CuotaRecargo
        return taxes

    def _get_sii_tax_linee(self, cr, uid, tax_line, line, line_taxes):
        tax_type = tax_line.amount * 100
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxes = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        tax_sii = {
            "BaseImponible":taxes['total'],
        }
        return tax_sii
    
    
    def _update_sii_tax_linee(self, cr, uid, taxes, tax_line, line, line_taxes):
        tax_type = tax_type = tax_line.amount * 100
        tax = self.pool.get('account.tax').browse(cr, uid, tax_line.id)
        if tax:
           taxesc = self.pool.get('account.tax').compute_all(cr, uid, [tax], (line.price_unit * (1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, line.invoice_id.partner_id)
        taxes[str(tax_type)]['BaseImponible'] += taxesc['total']
        return taxes

    
    def _get_sii_out_taxes(self, cr, uid, invoice):
        taxes_sii = {}
        taxes_f = {}
        taxes_to = {}
        taxes_fe = {}
        for line in invoice.invoice_line:
            for tax_line in line.invoice_line_tax_id:
                if tax_line.name in ['S_IVA21', 'S_IVA10', 'S_IVA4', 'S_IVA0', 'S_IVA0_IC']:
                    
                    if 'DesgloseFactura' not in taxes_sii:
                        taxes_sii['DesgloseFactura'] = {}
                    if tax_line.name in [
                        'S_IVA21', 'S_IVA10', 'S_IVA4', 'S_IVA0']:
                        if 'Sujeta' not in taxes_sii['DesgloseFactura']:
                            taxes_sii['DesgloseFactura']['Sujeta'] = {}
                        if tax_line.name in ['S_IVA0']:
                            if 'Exenta' not in taxes_sii['DesgloseFactura'][
                                'Sujeta']:
                                tax_type2 = tax_line.amount * 100
                                if str(tax_type2) not in taxes_fe.keys():
                                   taxes_fe[str(tax_type2)] = self._get_sii_tax_linee(cr, uid, tax_line, line, line.invoice_line_tax_id)
                                else:
                                   taxes_fe[str(tax_type2)] = self._update_sii_tax_linee(cr, uid, taxes_fe, tax_line, line, line.invoice_line_tax_id)
                                 
                                taxes_sii['DesgloseFactura']['Sujeta'][
                                    'Exenta'] = taxes_fe[str(tax_type2)]
                        if tax_line.name in [
                            'S_IVA21', 'S_IVA10', 'S_IVA4', 'S_IVA0_IC']:
                            if 'NoExenta' not in taxes_sii['DesgloseFactura'][
                                'Sujeta']:
                                taxes_sii['DesgloseFactura']['Sujeta'][
                                    'NoExenta'] = {}
                            if tax_line.name in ['S_IVA0_IC']:
                                TipoNoExenta = 'S2'
                            else:
                                TipoNoExenta = 'S1'  
                            taxes_sii['DesgloseFactura']['Sujeta']['NoExenta'][
                                'TipoNoExenta'] = TipoNoExenta
                            if 'DesgloseIVA' not in taxes_sii[
                                'DesgloseFactura']['Sujeta']['NoExenta']:
                                taxes_sii['DesgloseFactura']['Sujeta'][
                                    'NoExenta']['DesgloseIVA'] = {}
                                taxes_sii['DesgloseFactura']['Sujeta'][
                                    'NoExenta']['DesgloseIVA'][
                                        'DetalleIVA'] = []
                            tax_type = tax_line.amount * 100
                            if str(tax_type) in taxes_f.keys():
                                taxes_f = self._update_sii_tax_line(cr, uid, taxes_f, tax_line, line, line.invoice_line_tax_id)
                            else:
                                taxes_f[str(tax_type)] = self._get_sii_tax_line(cr, uid, tax_line, line, line.invoice_line_tax_id)
        if len(taxes_f) > 0:
            for key, line in taxes_f.iteritems():
                taxes_sii['DesgloseFactura']['Sujeta']['NoExenta'][
                    'DesgloseIVA']['DetalleIVA'].append(line)
        """ if len(taxes_to) > 0:
            for key, line in taxes_to.iteritems():
                taxes_sii['DesgloseTipoOperacion']['PrestacionServicios'][
                    'Sujeta']['NoExenta']['DesgloseIVA'][
                        'DetalleIVA'].append(line)"""
        return taxes_sii

    
    def _get_sii_in_taxes(self, cr, uid, invoice): 
        taxes_sii = {}
        taxes_f = {}
        pasivo = 0
        for line in invoice.invoice_line:
            for tax_line in line.invoice_line_tax_id:
                if tax_line.name in ['P_IVA21_BC', 'P_IVA21_SP', 'P_IVA10_BC', 'P_IVA10_SP', 'P_IVA4_BC', 'P_IVA4_SP', 'P_IVA0_BC']:
                    if tax_line.name in ['P_IVA21_SP', 'P_IVA10_SP', 'P_IVA4_SP']:
                       pasivo = 1
                       if 'InversionSujetoPasivo' not in taxes_sii:
                          taxes_sii['InversionSujetoPasivo'] = {}
                       if 'DetalleIVA' not in taxes_sii['InversionSujetoPasivo']:
                          taxes_sii['InversionSujetoPasivo']['DetalleIVA'] = []
                    else:
                       if 'DesgloseIVA' not in taxes_sii:     
                          taxes_sii['DesgloseIVA'] = {}
                       if 'DetalleIVA' not in taxes_sii['DesgloseIVA']:
                          taxes_sii['DesgloseIVA']['DetalleIVA'] = []

                    tax_type = tax_line.amount * 100
                    if str(tax_type) not in taxes_f.keys():
                        taxes_f[str(tax_type)] = self._get_sii_tax_linep(cr, uid, tax_line, line, line.invoice_line_tax_id)
                    else:
                        taxes_f = self._update_sii_tax_linep(cr, uid, taxes_f, tax_line, line, line.invoice_line_tax_id)

        for key, line in taxes_f.iteritems():
            if pasivo == 1:  
               taxes_sii['InversionSujetoPasivo']['DetalleIVA'].append(line)
            else:
               taxes_sii['DesgloseIVA']['DetalleIVA'].append(line)
        return taxes_sii
    
    def _get_invoices(self, cr, uid, ids, company, invoice):
        invoice_date = self._change_date_format(cr, uid, invoice.date_invoice)
        Ejercicio = invoice.period_id.fiscalyear_id.date_start[0:4]
        Periodo = invoice.period_id.date_start[5:7]

        if invoice.type in ['out_invoice']:
            TipoDesglose = self._get_sii_out_taxes(cr, uid, invoice)
            invoices = {
                "IDFactura":{
                    "IDEmisorFactura": {
                        "NIF": company.vat[2:]
                        },
                    "NumSerieFacturaEmisor": invoice.number,
                    "FechaExpedicionFacturaEmisor": invoice_date },
                "PeriodoImpositivo": {
                    "Ejercicio": Ejercicio,
                    "Periodo": Periodo
                    },
                "FacturaExpedida": {
                    "TipoFactura": "F1",
                    "ClaveRegimenEspecialOTrascendencia": "01",
                    "DescripcionOperacion": invoice.number,
                    "Contraparte": {
                        "NombreRazon": invoice.partner_id.name[0:40],
                        "NIF": invoice.partner_id.vat[2:]
                        },
                    "TipoDesglose": TipoDesglose
                }
            }

        if invoice.type in ['in_invoice']:
            TipoDesglose = self._get_sii_in_taxes(cr, uid, invoice)
            invoices = {
                "IDFactura":{
                    "IDEmisorFactura": {
                        "NIF": invoice.partner_id.vat[2:]
                        },
                    "NumSerieFacturaEmisor": invoice.reference,
                    "FechaExpedicionFacturaEmisor": invoice_date},
                "PeriodoImpositivo": {
                    "Ejercicio": Ejercicio,
                    "Periodo": Periodo
                    },
                "FacturaRecibida": {
                    "TipoFactura": "F1",
                    "ClaveRegimenEspecialOTrascendencia": "01",
                    "DescripcionOperacion": invoice.number,
                    "DesgloseFactura": TipoDesglose,
                    "Contraparte": {
                        "NombreRazon": invoice.partner_id.name[0:40],
                        "NIF": invoice.partner_id.vat[2:]
                        },
                    "FechaRegContable": invoice_date,
                    "CuotaDeducible": invoice.amount_tax
                }
            }

        if invoice.type in ['out_refund']:
            TipoDesglose = self._get_sii_out_taxes(cr, uid, invoice)
            invoices = {
                "IDFactura":{
                    "IDEmisorFactura": {
                        "NIF": company.vat[2:]
                        },
                    "NumSerieFacturaEmisor": invoice.number,
                    "FechaExpedicionFacturaEmisor": invoice_date },
                "PeriodoImpositivo": {
                    "Ejercicio": Ejercicio,
                    "Periodo": Periodo
                    },
                "FacturaExpedida": {
                    "TipoFactura": "R1",
                    "TipoRectificativa": "I", #POR DIFERENCIA S POR SUSTITUCION - INDICAR MAS CAMPOS.
                    "ClaveRegimenEspecialOTrascendencia": "01",
                    "DescripcionOperacion": invoice.number,
                    "Contraparte": {
                        "NombreRazon": invoice.partner_id.name[0:40],
                        "NIF": invoice.partner_id.vat[2:]
                        },
                    "TipoDesglose": TipoDesglose
                }
            }

        if invoice.type in ['in_refund']:
            TipoDesglose = self._get_sii_in_taxes(cr, uid, invoice)
            invoices = {
                "IDFactura":{
                    "IDEmisorFactura": {
                        "NIF": company.vat[2:]
                        },
                    "NumSerieFacturaEmisor": invoice.reference,
                    "FechaExpedicionFacturaEmisor": invoice_date },
                "PeriodoImpositivo": {
                    "Ejercicio": Ejercicio,
                    "Periodo": Periodo
                    },
                "FacturaExpedida": {
                    "TipoFactura": "R1",
                    "TipoRectificativa": "I", #POR DIFERENCIA S POR SUSTITUCION - INDICAR MAS CAMPOS.
                    "ClaveRegimenEspecialOTrascendencia": "01",
                    "DescripcionOperacion": invoice.number,
                    "Contraparte": {
                        "NombreRazon": invoice.partner_id.name[0:40],
                        "NIF": invoice.partner_id.vat[2:]
                        },
                    "TipoDesglose": TipoDesglose
                }
            }

        return invoices
    
    
    def _connect_sii(self, cr, uid, wsdl):
        publicCrt = self.pool.get('ir.config_parameter').get_param(cr, uid, 
            'l10n_es_aeat_sii.publicCrt', False)
        privateKey = self.pool.get('ir.config_parameter').get_param(cr, uid, 
            'l10n_es_aeat_sii.privateKey', False)

        session = Session()
        session.cert = (publicCrt, privateKey)
        transport = Transport(session=session)

        history = HistoryPlugin()
        client = Client(wsdl=wsdl,transport=transport,plugins=[history])
        return client

    
    def _send_invoice_to_sii(self, cr, uid, ids):
        for invoice in self.pool.get('account.invoice').browse(cr, uid, ids):
            company = invoice.company_id
            port_name = ''
            idintracom = self.pool.get('account.fiscal.position').search(cr, uid, [('name', '=', 'Régimen Intracomunitario')])
            if invoice.fiscal_position.id == idintracom[0]:
                wsdl = company.wsdl_ic
                client = self._connect_sii(cr, uid, wsdl)
                port_name = 'SuministroOpIntracomunitarias'
                if company.sii_test:
                    port_name += 'Pruebas'
            else:
             if invoice.type == 'out_invoice' or invoice.type == 'out_refund':
                wsdl = company.wsdl_out
                client = self._connect_sii(cr, uid, wsdl)
                port_name = 'SuministroFactEmitidas'
                if company.sii_test:
                    port_name += 'Pruebas'
             elif invoice.type == 'in_invoice' or invoice.type == 'in_refund':
                wsdl = company.wsdl_in
                client = self._connect_sii(cr, uid, wsdl)
                port_name = 'SuministroFactRecibidas'
                if company.sii_test:
                    port_name += 'Pruebas'
            serv = client.bind('siiService', port_name)
            if not invoice.sii_sent:
                TipoComunicacion = 'A0'
            else:
                TipoComunicacion = 'A1'
            
            header = self._get_header(cr, uid, invoice.id, company, TipoComunicacion)
            invoices = self._get_invoices(cr, uid, invoice.id, company, invoice)
            try:
                idintracom = self.pool.get('account.fiscal.position').search(cr, uid, [('name', '=', 'Régimen Intracomunitario')])
                if invoice.fiscal_position.id == idintracom[0]:
                   res = serv.SuministroLRDetOperacionIntracomunitaria(header, invoices)
                else:
                 if invoice.type == 'out_invoice' or invoice.type == 'out_refund':
                   res = serv.SuministroLRFacturasEmitidas(header, invoices)
                 elif invoice.type == 'in_invoice' or invoice.type == 'in_refund':
                    res = serv.SuministroLRFacturasRecibidas(header, invoices)
#                 TODO Factura Bienes de inversión
#                 elif invoice == 'Property Investiment':
#                     res = serv.SuministroLRBienesInversion(
#                         header, invoices)
#                 TODO Facturas intracomunitarias
#                 elif invoice.fiscal_position.id == self.env.ref(
#                     'account.fp_intra').id:
#                     res = serv.SuministroLRDetOperacionIntracomunitaria(
#                         header, invoices)
                if res['EstadoEnvio'] == 'Correcto':                   
                   self.write(cr, uid, invoice.id, {'sii_sent': True}) 
                self.write(cr, uid, invoice.id, {'sii_return': res})
            except Exception as fault:
                self.write(cr, uid, invoice.id, {'sii_return': fault})

    
    def invoice_validate(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).invoice_validate(cr, uid, ids, context=context)
        
        self._send_invoice_to_sii(cr, uid, ids)
        
        return res

account_invoice()

