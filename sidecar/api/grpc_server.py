"""
SGCI gRPC Server

To generate Python stubs from proto:
    python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/sgci.proto

For now, this uses grpclib for async support.
"""

import asyncio
import json
from typing import Optional

try:
    from grpclib.server import Server
    from grpclib.utils import graceful_exit
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

from engine.rsct import RSCTEngine
from store.certificates import CertificateStore

# Initialize engine and store
engine = RSCTEngine()
store = CertificateStore()


if GRPC_AVAILABLE:
    from grpclib.const import Status
    from grpclib.exceptions import GRPCError

    class SGCIService:
        """SGCI gRPC service implementation."""

        async def Certify(self, stream) -> None:
            """Pre-execution gate check."""
            request = await stream.recv_message()

            cert = engine.certify(
                prompt=request.prompt,
                model_id=request.model_id if request.HasField('model_id') else None,
                context=request.context if request.HasField('context') else None,
                policy=request.policy if request.HasField('policy') else 'default',
            )
            store.store(cert)

            # Convert to proto response
            response = self._cert_to_proto(cert)
            await stream.send_message(response)

        async def Validate(self, stream) -> None:
            """Post-execution validation feedback."""
            request = await stream.recv_message()

            # Verify certificate exists
            cert = store.get(request.certificate_id)
            if cert is None:
                raise GRPCError(Status.NOT_FOUND, "Certificate not found")

            # Record validation
            adjustment = engine.record_validation(
                certificate_id=request.certificate_id,
                validation_type=self._validation_type_to_str(request.validation_type),
                score=request.score,
                failed=request.failed,
            )

            # Build response (simplified - needs proto message construction)
            await stream.send_message({
                'recorded': True,
                'adjustment': adjustment,
            })

        async def Audit(self, stream) -> None:
            """Compliance audit export."""
            request = await stream.recv_message()

            certs = store.list(limit=request.limit or 100)

            if request.format == "SR11-7":
                records = [engine.format_sr117(c) for c in certs]
            else:
                records = certs

            # Encode records as JSON bytes
            encoded_records = [json.dumps(r).encode() for r in records]

            await stream.send_message({
                'certificate_count': len(records),
                'format': request.format or 'JSON',
                'records': encoded_records,
            })

        async def GetCertificate(self, stream) -> None:
            """Get certificate by ID."""
            request = await stream.recv_message()

            cert = store.get(request.certificate_id)
            if cert is None:
                raise GRPCError(Status.NOT_FOUND, "Certificate not found")

            response = self._cert_to_proto(cert)
            await stream.send_message(response)

        async def Health(self, stream) -> None:
            """Health check."""
            await stream.recv_message()
            await stream.send_message({
                'status': 'healthy',
                'service': 'swarm-it-sidecar',
            })

        def _cert_to_proto(self, cert: dict) -> dict:
            """Convert certificate dict to proto-compatible dict."""
            decision_map = {
                'EXECUTE': 1,
                'REPAIR': 2,
                'DELEGATE': 3,
                'BLOCK': 4,
                'REJECT': 5,
            }
            return {
                'id': cert['id'],
                'timestamp': cert['timestamp'],
                'R': cert['R'],
                'S': cert['S'],
                'N': cert['N'],
                'kappa_gate': cert['kappa_gate'],
                'sigma': cert['sigma'],
                'decision': decision_map.get(cert['decision'], 0),
                'gate_reached': cert['gate_reached'],
                'reason': cert['reason'],
                'allowed': cert['allowed'],
                'kappa_H': cert.get('kappa_H'),
                'kappa_L': cert.get('kappa_L'),
                'kappa_interface': cert.get('kappa_interface'),
                'weak_modality': cert.get('weak_modality'),
                'is_multimodal': cert.get('is_multimodal', False),
            }

        def _validation_type_to_str(self, vtype: int) -> str:
            """Convert proto enum to string."""
            type_map = {
                1: 'TYPE_I',
                2: 'TYPE_II',
                3: 'TYPE_III',
                4: 'TYPE_IV',
                5: 'TYPE_V',
                6: 'TYPE_VI',
            }
            return type_map.get(vtype, 'TYPE_I')


    async def run_grpc_server(host: str = '0.0.0.0', port: int = 9090):
        """Run the gRPC server."""
        server = Server([SGCIService()])
        with graceful_exit([server]):
            await server.start(host, port)
            print(f"gRPC server running on {host}:{port}")
            await server.wait_closed()


    if __name__ == '__main__':
        asyncio.run(run_grpc_server())

else:
    # Fallback when grpclib not installed
    def run_grpc_server(*args, **kwargs):
        raise ImportError(
            "gRPC support requires grpclib. Install with: pip install grpclib"
        )
