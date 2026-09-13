VF LICENCAS ONLINE — PRONTO

Objetivo: servidor HTTPS permanente para validar o Excel VF sem depender do telefone.

API:
GET /health
POST /validate
POST /admin/generate
POST /admin/block
POST /admin/unblock

Deploy:
1) Coloque estes arquivos num repositório Git.
2) Crie um Web Service Python no Render e conecte o repositório.
3) Defina VF_ADMIN_KEY como segredo seu.
4) O endereço HTTPS do serviço será usado no Excel:
   https://SEU-ENDERECO/validate

Planos: MENSAL=30 dias; TRIMESTRAL=90 dias.
NUNCA coloque VF_ADMIN_KEY no Excel do cliente.
